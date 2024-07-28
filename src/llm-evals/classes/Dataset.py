from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
from classes.Message import Message
from classes.Thread import Thread
from classes.Turn import Turn
from classes.Completion import Completion
import json
import peewee as pw
import sqlite3
import copy
from pprint import pprint
from collections import OrderedDict
from datetime import datetime


class Dataset(BaseModel):
    """Holds a dataset, e.g. a jsonl file"""

    id = pw.IntegerField(primary_key=True)
    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="datasets")
    filename = pw.TextField()
    datatype = pw.TextField(null=True)
    contents = pw.TextField(null=True)  # raw contents

    # In line with LangGraph expectations, we assume n=1 for all outputs of LLMs
    # However, each node can append list with length 2+ to the message queue

    # Thread - conversation
    # Turn - adjacent messages from the same agent
    # Message -
    #   role - human or ai, user or assistant
    #   text - empty string or non-empty
    #   list of 0+ Tool Calls
    #   post-processing - add a turn_id
    #   additional_kwargs JSON
    # ToolUse
    #   foreign keys to "invoker" message and "function output" message
    #   message that invoked it - foreign key
    #   parameters of the input
    #   result of tool call
    # Metric
    #   granularity type
    #   foreign key to the object

    # **each entry from LangGraph is a LIST of completions - usually with length 1

    # Completion - has one bit of text content, and 0+ ToolCalls
    # ToolCall - tool call (and response!) associated with the completion
    #   completion_id
    #   message_id
    #   turn_id

    def load_data(self):

        if self.filename.endswith(".jsonl"):
            self.datatype = "json"
            self.load_jsonl(dataset=self)
        elif is_sqlite_file(self.filename):
            self.datatype = "sqlite"
            self.load_langgraph_sqlite()
        else:
            raise Exception(
                f"Each Data File must be either a jsonl or sqlite file. You provided the file: {self.filename}"
            )


def is_sqlite_file(filepath):
    # Open the file in binary mode
    with open(filepath, "rb") as file:
        header = file.read(16)
    # Check if the header matches the SQLite format header
    return header == b"SQLite format 3\x00"
