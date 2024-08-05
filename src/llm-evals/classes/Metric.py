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
# from classes.DatasetRow import DatasetRow
from classes.Thread import Thread
from classes.Turn import Turn
from classes.Message import Message
from classes.ToolCall import ToolCall
from playhouse.shortcuts import model_to_dict
import copy


class Metric(BaseModel):
    """Holds a single metric/property computed based one just ONE turn"""

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="turnproperties")
    dataset = pw.ForeignKeyField(Dataset, backref="turnproperties")
    thread = pw.ForeignKeyField(Thread, backref="turnproperties")
    turn = pw.ForeignKeyField(Turn, null=True, backref="turnproperties") # Only defined for Turn metrics
    message = pw.ForeignKeyField(Message, null=True, backref="turnproperties") # Only defined for Message metrics
    toolcall = pw.ForeignKeyField(ToolCall, null=True, backref="turnproperties") # Only defined for ToolCall metrics
    
    evaluation_name = pw.TextField()
    evaluation_type = pw.TextField()
    metric_name = pw.TextField()
    # metric_type = pw.TextField() # TODO: Some parts of the code use "metric_tye" and others use "evaluation_type" - choose one for consistency 
    metric_level = pw.TextField()
    metric_value = pw.FloatField(null=True)  # necessary if rubric result is INVALID
    kwargs = pw.TextField()
    source = (
        pw.TextField()
    )  # TODO - make another table for this? But maybe not, because this also contains filled-in rubrics
    depends_on = pw.TextField()
    rubric_prompt = pw.TextField(null=True)
    rubric_completion = pw.TextField(null=True)
    rubric_model = pw.TextField(null=True)
    rubric_completion_tokens = pw.IntegerField(null=True)
    rubric_prompt_tokens = pw.IntegerField(null=True)
    rubric_score = pw.TextField(null=True)
