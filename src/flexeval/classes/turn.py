import copy
import json
import logging

import peewee as pw
from playhouse.shortcuts import model_to_dict

from flexeval.classes.base import BaseModel
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.thread import Thread
from flexeval.configuration import completion_functions

logger = logging.getLogger(__name__)


class Turn(BaseModel):
    """Holds a single turn
    In a conversational exchange, each 'Turn' holds information
    from 1 or more outputs from the same source or role in sequence
    """

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="turns")
    dataset = pw.ForeignKeyField(Dataset, backref="turns")
    thread = pw.ForeignKeyField(Thread, backref="turns")
    index_in_thread = pw.IntegerField()
    role = pw.TextField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_to_evaluate = []

    def get_completion(self):
        # only get a completion if this is the final turn - we probably don't want to branch from mid-conversation
        if self.is_final_turn_in_input:
            completion_config = json.loads(self.evalsetrun.completion_llm)
            completion_fn_name = completion_config.get("function_name", None)
            completion_function_kwargs = completion_config.get("kwargs", None)

            # Check if the function name exists in the global namespace and call it
            if hasattr(completion_functions, completion_fn_name) and hasattr(
                completion_functions, completion_fn_name
            ):
                completion_function = getattr(
                    completion_functions, completion_fn_name, None
                )
                completion = completion_function(
                    conversation_history=self.get_formatted_prompt(
                        include_system_prompt=False
                    ),
                    **completion_function_kwargs,
                )
            else:
                logger.warning(
                    "In completion_functions.py: No callable function named "
                    + completion_fn_name
                    + " found."
                )
                completion = None

            # "completion" will be the output of an existing completion function
            # We need to make the message object
            # and probably also a turn object

            # which means it'll have a structure like this
            # TODO - make this a requirement of the completion functions?
            #       - make the completion function just return content?
            # {"choices": [{"message": {"content": "hi", "role": "assistant"}}]}
            result = model_to_dict(self, exclude=[self.id])
            result["evalsetrun"] = self.evalsetrun
            result["dataset"] = self.dataset
            result["datasetrow"] = self.datasetrow
            result["turn_number"] = self.turn_number + 1
            result["role"] = "assistant"
            result["context"] = self.get_formatted_prompt(include_system_prompt=False)
            result["is_final_turn_in_input"] = False  # b/c it's not in input
            self.is_final_turn_in_input = False
            result["is_completion"] = True
            result["completion"] = completion
            result["model"] = completion.get("model", None)
            result["prompt_tokens"] = completion.get("usage", {}).get(
                "prompt_tokens", None
            ) / len(completion.get("choices", [1]))
            result["completion_tokens"] = completion.get("usage", {}).get(
                "completion_tokens", None
            ) / len(
                completion.get("choices", [1])
            )  # TODO - use tiktoken here instead?? this will just give the average

            result_list = []
            for ix, choice in enumerate(completion["choices"]):
                temp = copy.deepcopy(result)
                temp["tool_used"] = choice["message"].get("tool_calls", None)
                temp["turn"] = [choice["message"]]
                temp["content"] = choice["message"]["content"]
                temp["completion_number"] = ix + 1
                result_list.append(temp)

            return result_list
        else:
            return None

    def get_context(self, include_system_prompt=False) -> list[dict[str, str]]:
        """
        Context is the context of the first message in the turn
        """
        context = ""
        for message in self.messages:
            context = message.context
            break
        context = json.loads(context)
        if not include_system_prompt:
            context = [
                cur_dict for cur_dict in context if cur_dict.get("role") != "system"
            ]
        return context

    def get_formatted_prompt(self, include_system_prompt=False):
        formatted_prompt = []
        if include_system_prompt:
            if hasattr(self, "system_prompt"):
                # TODO this is a bit hacky; it allows for an override of the system prompt by setting it on the Turn object
                system_prompt = self.system_prompt
            else:
                system_prompt = self.thread.system_prompt
            # if system prompt not available in this thread, we have nothing to include
            if system_prompt is not None:
                formatted_prompt.append({"role": "system", "content": system_prompt})

        # context = json.loads(self.context)
        context = self.get_context()

        if len(context) > 0:
            formatted_prompt += context  # TODO - we might just want a subset of this

        formatted_prompt += self.get_content()
        return formatted_prompt

    def get_content(self, include_toolcalls=True, include_tool_messages=True):
        """
        Content is a list of dictionaries where each dictionary
        contains the role and content of messages and tool calls
        in the turn. Each tool call appears after the message it's
        associated with. If toolcalls are not desired, pass False
        to include_toolcalls.
        """
        content = []
        for message in self.messages:
            if include_tool_messages or message.langgraph_message_type != "ToolMessage":
                content.append({"role": message.role, "content": message.content})
            if include_toolcalls:
                for toolcall in message.toolcalls:
                    content.append(toolcall.get_dict_representation())

        return content

    def format_input_for_rubric(
        self, include_system_prompt: bool = False, include_tool_messages: bool = False
    ):
        """This is the 'public' method that returns the info for this Turn"""
        output_minus_completion = ""
        if include_system_prompt:
            output_minus_completion.append(
                {"role": "system", "content": self.system_prompt}
            )

        for msg in self.get_context():  # input[:-1]:
            # this outputs user: XYZ, or assistant: 123
            if len(msg["content"]) > 0 and (
                include_tool_messages or msg.get("langgraph_role") != "tool"
            ):
                output_minus_completion += f"{msg['role']}: {msg['content']}\n"
        # Including role as prefix to account for both tool and assistant
        completion = ""
        for msg in self.get_content(include_tool_messages=include_tool_messages):
            if len(msg["content"]) > 0:
                completion += f"{msg['role']}: {msg['content']}\n"
        # completion = f"{self.get_content()['content']}"
        output = output_minus_completion + completion

        tool_call_text = ""
        for tc in self.toolcalls:
            printme = True
            # if there's a property called tc.additional_kwargs and it evalues to False...don't print
            if hasattr(tc, "additional_kwargs"):
                if not json.loads(tc.additional_kwargs).get("print", False):
                    printme = False
            if printme:
                tool_call_text += """

    Function name: {function_name}
    Input arguments: {args}
    Function output: {response_content}
    """.format(
                    function_name=tc.function_name,
                    args=tc.args,
                    response_content=tc.response_content,
                )

        # output - all turns
        # output_minus_completion - all turns except the last
        # completion - last turn
        # tool_call_text - all tool calls
        return output, output_minus_completion, completion, tool_call_text
