import os
from pathlib import Path
import sys

import pydantic
import json
import peewee as pw
from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.Thread import Thread
from playhouse.shortcuts import model_to_dict
import copy
import helpers

# from configuration import function_metrics
from configuration import completion_functions
import inspect
import string
from typing import ForwardRef, get_args


class Turn(BaseModel):
    """Holds a single turn
    In a conversational exchange, each 'Turn' holds information
    from 1 or more outputs from the same source or role in sequence
    """

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="turns")
    dataset = pw.ForeignKeyField(Dataset, backref="turns")
    thread = pw.ForeignKeyField(Thread, backref="turns")
    role = pw.TextField()

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
                completion_function = getattr(completion_functions, completion_fn_name, None)
                completion = completion_function(
                    conversation_history=self.get_formatted_prompt(
                        include_system_prompt=False
                    ),
                    **completion_function_kwargs,
                )
            else:
                print(
                    "In completion_functions.py: No callable function named "
                    + completion_fn_name
                    + " found."
                )
                completion = None

            # "completion" will be the output of an existing completion function
            # We need to make the message object
            # and probably also a turn object

            # which means it'll have a structure like this
            # TODO - make this a requirement of the completion functions?
            #       - make the completion function just return content?
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

    def get_context(self):
        '''
        Context is the context of the first message in the turn
        '''
        context = ""
        for message in self.messages:
            context = message.context
            break
        return json.loads(context)
    

    def get_formatted_prompt(self, include_system_prompt=False):
        formatted_prompt = []
        if include_system_prompt:
            formatted_prompt.append({"role": "system", "content": self.system_prompt})
        #context = json.loads(self.context)
        context = self.get_context()

        if len(context) > 0:
            formatted_prompt += context  # TODO - we might just want a subset of this
        
        formatted_prompt += self.get_content()
        # for t in json.loads(self.turn):
        #     formatted_prompt.append({"role": t["role"], "content": t["content"]})
        return formatted_prompt
    
    def get_content(self):
        '''
        Content is a list of dictionaries where each dictionary contains the role and content of messages
        in the turn
        '''
        content = []
        for message in self.messages:
            content.append({"role": message.role, "content": message.content})
        return content

    def format_input_for_rubric(self):
        input = self.get_formatted_prompt()
        output_minus_completion = ""
        for i in input[:-1]:
            output_minus_completion += f"{i['role']}: {i['content']}\n"
        completion = f"{input[-1]['role']}: {input[-1]['content']}\n"
        output = output_minus_completion + completion
        # output - all turns
        # output_minus_completion - all turns except the last
        # completion - last turn
        return output, output_minus_completion, completion

