from classes.BaseModel import BaseModel
from classes.Dataset import Dataset
from classes.EvalSetRun import EvalSetRun
import json
import peewee as pw
import copy


class Thread(BaseModel):
    """Class for holding a single thread / converseation
    This corresponds to a single row in a jsonl file
    or a single 'thread_id' in a langgraph checkpoint database"""

    id = pw.IntegerField(primary_key=True)
    dataset = pw.ForeignKeyField(Dataset, backref="threads")
    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="threads")

    langgraph_thread_id = pw.TextField(null=True)
    system_prompt = pw.TextField(null=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_to_evaluate = []

    def get_content(self):
        """
        Content is a list of dictionaries where each dictionary contains the
        role and content of messages and tool calls in the thread
        """
        content = []
        for turn in self.turns:
            content = content + turn.get_content()
        return content

    # TODO - test this!
    def format_input_for_rubric(self):
        input = self.get_formatted_prompt()
        output_minus_completion = ""
        for i in input[:-1]:
            output_minus_completion += f"{i['role']}: {i['content']}\n"
        completion = f"{input[-1]['role']}: {input[-1]['content']}\n"
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

    def get_formatted_prompt(self, include_system_prompt=False):
        formatted_prompt = []
        if include_system_prompt:
            formatted_prompt.append({"role": "system", "content": self.system_prompt})

        formatted_prompt += self.get_content()

        return formatted_prompt

    def get_content(self, include_toolcalls=True):
        """
        Content is a list of dictionaries where each dictionary
        contains the role and content of messages and tool calls
        in the turn. Each tool call appears after the message it's
        associated with. If toolcalls are not desired, pass False
        to include_toolcalls.
        """
        content = []
        for message in self.messages:
            content.append({"role": message.role, "content": message.content})
            if include_toolcalls:
                for toolcall in message.toolcalls:
                    content.append(toolcall.get_dict_representation())

        return content

    # def get_turn_components(self):
    #     return json.dumps(input)

    # def get_ideals(self):
    #     return json.loads(self.ideals)

    # def tally_tokens(self):
    #     input_list = json.loads(self.input)
    #     self.completion_tokens, self.prompt_tokens = 0, 0
    #     for entry in input_list:
    #         self.completion_tokens += entry.get("completion_tokens", 0)
    #         self.prompt_tokens += entry.get("prompt_tokens", 0)
