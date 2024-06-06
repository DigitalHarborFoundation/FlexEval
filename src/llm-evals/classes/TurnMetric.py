import os
from pathlib import Path
import sys
import inspect
import string
import pydantic
import json
import peewee as pw
from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.DatasetRow import DatasetRow
from classes.Turn import Turn
from playhouse.shortcuts import model_to_dict
import copy


class TurnMetric(BaseModel):
    """Holds a single metric/property computed based one just ONE turn"""

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="turnproperties")
    dataset = pw.ForeignKeyField(Dataset, backref="turnproperties")
    datasetrow = pw.ForeignKeyField(DatasetRow, backref="turnproperties")
    turn = pw.ForeignKeyField(Turn, backref="turnproperties")

    function_name = pw.TextField()
    name = pw.TextField()
    value = pw.FloatField(null=True)  # necessary if rubric result is INVALID
    kwargs = pw.TextField()
    source = pw.TextField()
    depends_on = pw.TextField()
    type = pw.TextField()
    rubric_completion = pw.TextField(null=True)
    rubric_model = pw.TextField(null=True)
    rubric_completion_tokens = pw.IntegerField(null=True)
    rubric_prompt_tokens = pw.IntegerField(null=True)
    rubric_score = pw.TextField(null=True)
