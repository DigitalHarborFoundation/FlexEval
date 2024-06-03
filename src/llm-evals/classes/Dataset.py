import os
from pathlib import Path
import sys
from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
import pydantic
import json
import peewee as pw


class Dataset(BaseModel):
    """Holds a dataset, e.g. a jsonl file"""

    id = pw.IntegerField(primary_key=True)
    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="datasets")
    filename = pw.TextField()
    contents = pw.TextField()

    def get_rows(self):
        return [json.loads(row) for row in self.contents.splitlines()]
