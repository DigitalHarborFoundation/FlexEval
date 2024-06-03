import os
from pathlib import Path
import sys

import pydantic
import json
import peewee as pw
from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.DatasetRow import DatasetRow
from playhouse.shortcuts import model_to_dict
import copy

# from configuration.completion_functions import *
from configuration import completion_functions as cf


class Turn(BaseModel):
    """Holds a single turn"""

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="turns")
    dataset = pw.ForeignKeyField(Dataset, backref="turns")
    datasetrow = pw.ForeignKeyField(DatasetRow, backref="turns")

    turn_number = pw.IntegerField()  # 1-indexed
    role = pw.TextField()  # user or assistant - 'tools' are counted as assistants
    tool_used = pw.TextField(null=True)
    system_prompt = pw.TextField()
    context = pw.TextField()  # all previous turns + system prompt
    turn = pw.TextField()
    content = pw.TextField()  # concatenated contents fields
    is_final_turn_in_input = pw.BooleanField()
    is_completion = pw.BooleanField()
    prompt_tokens = pw.TextField(null=True)
    completion_tokens = pw.TextField(null=True)
    completion_number = pw.IntegerField(null=True)

    def get_completion(self, include_system_prompt=False):
        # only get a completion if this is the final turn - we probably don't want to branch from mid-conversation
        if self.is_final_turn_in_input:
            completion_config = json.loads(self.evalsetrun.completion_llm)
            completion_fn_name = completion_config.get("function_name", None)
            completion_function_kwargs = completion_config.get("kwargs", None)

            # Check if the function name exists in the global namespace and call it

            if hasattr(cf, completion_fn_name) and hasattr(cf, completion_fn_name):
                completion_function = getattr(cf, completion_fn_name, None)
                completion = completion_function(
                    conversation_history=self.get_formatted_prompt(
                        include_system_prompt=False
                    ),
                    **completion_function_kwargs
                )
            else:
                print(
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

    def get_formatted_prompt(self, include_system_prompt=False):
        formatted_prompt = []
        if include_system_prompt:
            formatted_prompt.append({"role": "system", "content": self.system_prompt})
        context = json.loads(self.context)
        if len(context) > 0:
            formatted_prompt += context  # TODO - we might just want a subset of this
        for t in json.loads(self.turn):
            formatted_prompt.append({"role": t["role"], "content": t["content"]})
        return formatted_prompt
