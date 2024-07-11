from classes.BaseModel import BaseModel
from classes.Dataset import Dataset
from classes.EvalSetRun import EvalSetRun
import json
import peewee as pw
import copy


class Conversation(BaseModel):
    """Class for holding a single row of a dataset, i.e. one conversation"""

    id = pw.IntegerField(primary_key=True)
    dataset = pw.ForeignKeyField(Dataset, backref="rows")
    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="rows")
    input = pw.TextField()
    ideals = pw.TextField(
        null=True
    )  # dictionary mapping between eval name and ideal value
    prompt_tokens = pw.IntegerField(null=True)
    completion_tokens = pw.IntegerField(null=True)

    def get_turn_components(self):
        return json.dumps(input)

    def get_ideals(self):
        return json.loads(self.ideals)

    def tally_tokens(self):
        input_list = json.loads(self.input)
        self.completion_tokens, self.prompt_tokens = 0, 0
        for entry in input_list:
            self.completion_tokens += entry.get("completion_tokens", 0)
            self.prompt_tokens += entry.get("prompt_tokens", 0)
