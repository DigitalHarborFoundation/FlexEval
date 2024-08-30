import os
from pathlib import Path
import sys

import pydantic
import json
import peewee as pw
from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.Message import Message
from classes.Thread import Thread
from classes.Turn import Turn
from playhouse.shortcuts import model_to_dict
import copy
import helpers

from configuration import completion_functions


class ToolCall(BaseModel):
    """Holds a single component of a single turn
    Corresponds to one output of a node in LangGraph
    or one Turn in jsonl
    """

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="toolcalls")
    dataset = pw.ForeignKeyField(Dataset, backref="toolcalls")
    thread = pw.ForeignKeyField(Thread, backref="toolcalls")
    message = pw.ForeignKeyField(Message, backref="toolcalls")
    turn = pw.ForeignKeyField(Turn, backref="toolcalls")

    function_name = pw.TextField()
    args = pw.TextField()
    tool_call_id = pw.TextField()
    response_content = pw.TextField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_to_evaluate = []

    def get_dict_representation(self) -> dict:
        """
        Get a dictionary representation of the content of this toolcall,
        suitable for passing to function metrics that need a standard Python
        data structure representation of a tool call.

        Keys in returned dictionary are role, content (for the response content),
        function_name, and args.
        """
        return {
            "role": "toolcall",
            "content": self.response_content,
            "args": self.args,
            "function_name": self.function_name,
        }
