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
