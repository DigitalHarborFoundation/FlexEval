import copy
import json
import logging

import peewee as pw
from playhouse.shortcuts import model_to_dict

from flexeval.classes.base import BaseModel
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.thread import Thread
from flexeval.classes.turn import Turn
from flexeval.classes.jsonview import JsonView
from flexeval.configuration import completion_functions

logger = logging.getLogger(__name__)


class Message(BaseModel):
    """Holds a single component of a single turn
    Corresponds to one output of a node in LangGraph
    or one Turn in jsonl
    """

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="messages")
    dataset = pw.ForeignKeyField(Dataset, backref="messages")
    thread = pw.ForeignKeyField(Thread, backref="messages")
    index_in_thread = pw.IntegerField()
    # must be null=True because we're adding it after create()
    turn = pw.ForeignKeyField(Turn, null=True, backref="messages")

    role = pw.TextField()  # user or assistant - 'tools' are counted as assistants
    content = pw.TextField()
    context = pw.TextField(null=True)  # Previous messages

    # metadata
    metadata = pw.TextField(default="{}", null=False)
    metadata_dict = JsonView("metadata")

    # helpers
    system_prompt = pw.TextField(null=True)
    is_flexeval_completion = pw.BooleanField(null=True)
    is_final_turn_in_input = pw.BooleanField(null=True)
    langgraph_print = pw.TextField(null=True)

    # language model stats
    tool_callslanggraph_print = pw.TextField(null=True)
    tool_call_ids = pw.TextField(null=True)
    n_tool_calls = pw.IntegerField(null=True)
    prompt_tokens = pw.IntegerField(null=True)
    completion_tokens = pw.IntegerField(null=True)
    model_name = pw.TextField(null=True)

    # langgraph metadata
    langgraph_ts = pw.TextField(null=True)
    langgraph_step = pw.IntegerField(null=True)
    langgraph_thread_id = pw.TextField(null=True)
    langgraph_checkpoint_id = pw.TextField(null=True)
    langgraph_parent_checkpoint_id = pw.TextField(null=True)
    langgraph_node = pw.TextField(null=True)
    langgraph_message_type = pw.TextField(null=True)
    langgraph_type = pw.TextField(null=True)
    langgraph_invocation_id = pw.TextField(null=True)
    # putting these at the end so the database is easier to browse
    langgraph_checkpoint = pw.TextField(null=True)
    langgraph_metadata = pw.TextField(null=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_to_evaluate = []

    def get_completion(self, include_system_prompt=False):
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
            # which generally means it'll have a structure like this
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

    def get_formatted_prompt(self, include_system_prompt=False) -> list[dict[str, str]]:
        formatted_prompt = []
        if include_system_prompt:
            formatted_prompt.append({"role": "system", "content": self.system_prompt})
        context = json.loads(self.context)
        if len(context) > 0:
            formatted_prompt += context  # TODO - we might just want a subset of this
        formatted_prompt.append({"role": self.role, "content": self.content})
        # for t in json.loads(self.turn):
        #     formatted_prompt.append({"role": t["role"], "content": t["content"]})
        return formatted_prompt

    def format_input_for_rubric(self):
        input = self.get_formatted_prompt()
        output_minus_completion = ""
        for i in input[:-1]:
            output_minus_completion += f"{i['role']}: {i['content']}\n"
        completion = f"{input[-1]['content']}"
        output = output_minus_completion + completion

        tool_call_text = ""
        for tc in self.toolcalls:
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

    def get_content(self) -> str:
        return self.content

    def get_context(self, include_system_prompt=False) -> list[dict[str, str]]:
        context = json.loads(self.context)
        if not include_system_prompt:
            context = [
                cur_dict for cur_dict in context if cur_dict.get("role") != "system"
            ]
        return context
