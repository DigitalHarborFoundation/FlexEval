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

from configuration import function_metrics
from configuration import completion_functions
import inspect
import string


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

    def compute_metrics(self):
        """we've defined a variable called metrics_to_evaluate
        it's a list we need to loop through
        each entry looks like this
        {
            'name': 'string_length',
            'type': 'function',
            'kwargs': {},
            'depends_on': []
        }
        """
        # there should be ONE entry per metric_name
        assert len(set([i["name"] for i in self.metrics_to_evaluate])) == len(
            self.metrics_to_evaluate
        ), "Metric names in `self.metrics_to_evaluate` are not unique! They must be."
        # we'll keep the results in a list
        # for each new metric, if it has dependencies, we'll need to make sure they're met - otherwise we won't run it
        evaluated_metrics = []
        for metric_to_evaluate in self.metrics_to_evaluate:
            # see if there's a dependency
            dependencies_are_all_met = True
            if metric_to_evaluate.get("depends_on", None) is not None:

                # if so, see if it's in the list of evaluated_metrics
                # it could concievably be missing if one of ITS dependencies was not met and it was not computed
                # if this is the case, we'll treat it as not being met

                # If there are no dependencies, this loop won't execute
                # if there are depenencies, ALL of them must be met
                # so not meeting ANY of them will short-circuit the loop and cause the eval to not evaluate
                # check all dependencies
                for dependency in metric_to_evaluate.get("depends_on", []):

                    # for each dependency, assume it's not met
                    # if it's in the list AND its values meet the criteria, it's met
                    dependency_is_met = False
                    for em in evaluated_metrics:
                        if em["name"] == dependency["name"]:
                            # if they are none, set to extreme values
                            max_value_criteria = dependency.get("min_value", -1e20)
                            min_value_criteria = dependency.get("max_value", 1e20)
                            if not (
                                em["value"] >= min_value_criteria
                                and em["value"] <= max_value_criteria
                            ):
                                dependency_is_met = True
                    if not dependency_is_met:
                        dependencies_are_all_met = False
                        # if even one dependency is not met - don't do the evaluation
                        break
            if dependencies_are_all_met:
                # pass through arguments, but add 'self' as the turn
                evaluated_metrics += compute_metric(turn=self, **metric_to_evaluate)

        return evaluated_metrics


def compute_metric(
    name: str, kwargs: dict, turn: Turn, type: str, depends_on: list = None
) -> list:

    if type == "function":
        metrics = compute_function_metric(
            metric_name=name, metric_kwargs=kwargs, turn=turn, depends_on=depends_on
        )
    elif type == "rubric":
        metrics = compute_rubric_metric(
            metric_name=name, metric_kwargs=kwargs, turn=turn, depends_on=depends_on
        )
    else:
        raise Exception(
            f"The argument metric_type provided to compute_metric is invalid. Must be one of `function` or `rubric`. You passed `{type}`."
        )
    return metrics


def compute_function_metric(
    metric_name: str, metric_kwargs: dict, turn: Turn, depends_on: list = None
):
    # this is NOT a method - it's a function b/c we want it to be able to return multiple metrics, if more than one is returned
    # they share most of the same information though so it's convenient to have them constructed similarly
    # will return a list of dictionaries

    # Check if the function name exists in the global namespace and call it

    if hasattr(function_metrics, metric_name) and callable(
        getattr(function_metrics, metric_name, None)
    ):
        metric_function = getattr(function_metrics, metric_name, None)
        metric_source = inspect.getsource(metric_function)

        # This gets the type of the first argument of the function
        input_type = next(
            iter(inspect.signature(metric_function).parameters.values())
        ).annotation

        # conditional depending on the type
        if input_type is str:
            # just pass in the content
            metrics_result = metric_function(turn.content, **metric_kwargs)
        elif input_type is list:
            # this is on a single turn - pass in the parsed list
            metrics_result = metric_function(json.loads(turn.turn), **metric_kwargs)
        else:
            raise Exception(
                f"Result type {input_type} is not supported in metric function {metric_name}"
            )

        base_result = {
            "turn": turn,
            "function_name": metric_name,
            "kwargs": metric_kwargs,
            "source": metric_source,
            "type": "function",
            "depends_on": depends_on,
        }
        # now deal with output
        if isinstance(metrics_result, float) or isinstance(metrics_result, int):
            result = copy.deepcopy(base_result)
            result["name"] = metric_name
            result["value"] = metrics_result
            return [result]
        elif isinstance(metrics_result, dict):
            result_list = []
            for k, v in metrics_result.items():
                result = copy.deepcopy(base_result)
                result["name"] = k
                result["value"] = float(v)
                result_list.append(result)
            return result_list
        elif isinstance(metrics_result, list):
            result_list = []
            for entry in metrics_result:
                result = copy.deepcopy(base_result)
                result["name"] = entry.get("name", None)
                result["value"] = float(entry.get("value", None))
                result_list.append(result)
            return result_list
        else:
            raise Exception(
                f"The metric type returned from `{metric_function}` is not a supported type. It must be one of `list`, `int`, `float`, or `dict`. You supplied `{type(metric_result)}`."
            )
    else:
        raise Exception(
            f"Metric with name `{metric_name}` was not found in function_metrics.py"
        )


def compute_rubric_metric(
    metric_name: str, metric_kwargs: dict, turn: Turn, depends_on: list
):

    # load metrics
    rubrics = json.loads(turn.evalsetrun.rubrics)
    assert (
        metric_name in rubrics
    ), f"You requested a rubric called `{metric_name}`, but only these were found:{rubrics.keys()}."

    prompt = rubrics.get(metric_name).get("prompt", "")

    # format input for rubric
    conversation, context, completion = turn.format_input_for_rubric()

    # The prompts will have three types
    # {context} -- everything BEFORE the last entry
    # {completion} -- new completion or last entry
    # {turn} -- just the current turn -- cannot be used with the other two

    # TODO - put these in the verification
    options = [("{turn}",), ("{context}", "{completion}"), ("{conversation}",)]
    for option1 in options:
        for option2 in options:
            if all([o in prompt for o in option1]):
                if option2 != option1:
                    for o2 in option2:
                        assert (
                            o2 not in prompt
                        ), f"Your rubric {metric_name} is has the template `{','.join([i  for i in option1]) }` and cannot also contain the template option `{o2}`."

    if "{turn}" in prompt:
        # single turn - do this for every turn
        populated_prompt = prompt.format(
            turn=completion
        )  # just use the entire conversation
    elif "{completion}" in prompt and "{context}" in prompt:
        # if 'do_completion', only evaluate completions
        if turn.evalsetrun.do_completion and turn.is_completion:
            populated_prompt = prompt.format(context=context, completion=completion)
        # TODO - if not do_completion, evaluate ???????every turn?????
        elif not turn.evalsetrun.do_completion:
            populated_prompt = prompt.format(context=context, completion=completion)
        else:
            return []
    elif "{conversation}" in prompt:
        # evaluate the full conversation UP TO the existing plot
        # it's a completion, OR we aren't doing completions so we just do this on the last turn
        if turn.evalsetrun.do_completion and turn.is_completion:
            populated_prompt = prompt.format(conversation=conversation)
        elif not turn.evalsetrun.do_completion:
            populated_prompt = prompt.format(conversation=conversation)
        else:
            return []
    else:
        return []

    choice_scores = rubrics.get(metric_name).get("choice_scores")
    # get rubric grader
    # TODO - this would be the rubric LLM
    grader_completion_function = json.loads(turn.evalsetrun.grader_llm)
    grader_completion_fn_name = grader_completion_function.get("function_name", None)
    grader_completion_fn_kwargs = grader_completion_function.get("kwargs", {})
    if hasattr(completion_functions, grader_completion_fn_name) and hasattr(
        completion_functions, grader_completion_fn_name
    ):
        completion_function = getattr(
            completion_functions, grader_completion_fn_name, None
        )
        DEFAULT_COT_TEMPLATE = "\nBefore answering, I will reason in a step-by-step manner as to get the right answer, then conclude with the answer in the format requested."
        ANSWER_PROMPT = f""""
First, write out in a step by step manner your reasoning to be sure that your conclusion is correct. Avoid simply stating the correct answer at the outset. Then print only a single choice from {list(choice_scores.keys())} (without quotes or punctuation) on its own line corresponding to the correct answer. At the end, repeat just the answer by itself on a new line.

Reasoning:""".strip()
        DEFAULT_EXTRACT_ANSWER_TEMPLATE = "\nGiven the above reasoning, the answer in the format requested by the question is:"
        completion = completion_function(
            conversation_history=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "assistant", "content": DEFAULT_COT_TEMPLATE},
                {"role": "user", "content": populated_prompt + ANSWER_PROMPT},
                {"role": "assistant", "content": DEFAULT_COT_TEMPLATE},
            ],
            **grader_completion_fn_kwargs,
        )
        completion_text = completion["choices"][0]["message"]["content"]

        # use logic from Evals
        # https://github.com/openai/evals/blob/d3dc89042ddee879a68a326fdb37716ee518640c/evals/elsuite/modelgraded/classify_utils.py#L29
        choice_scores["__invalid__"] = None

        def get_match(completion_text: str, choice_scores: dict):
            MATCH_FNS = {
                "include": lambda x, y: float(x in y),
                "exact": lambda x, y: float(x == y),
                "endswith": lambda x, y: x.endswith(y),
                "starts_or_endswith": lambda x, y: x.startswith(y) or x.endswith(y),
            }
            lines = completion_text.strip().split("\n")
            lines = lines[::-1]  # reverse lines
            for line in lines:
                line = line.strip()
                line = "".join(c for c in line if c not in string.punctuation)
                if not line:
                    continue
                for choice in choice_scores.keys():
                    if MATCH_FNS["starts_or_endswith"](line, choice):
                        return choice
            return "__invalid__"

        score = get_match(completion_text=completion_text, choice_scores=choice_scores)
        result = {
            "turn": turn,
            "name": metric_name,
            "function_name": metric_name,
            "kwargs": metric_kwargs,
            "depends_on": depends_on,
            "source": populated_prompt,
            "value": choice_scores[score],
            "type": "rubric",
            "rubric_completion": completion["choices"][0]["message"]["content"],
            "rubric_model": completion.get("model", None),
            "rubric_completion_tokens": completion.get("usage", {}).get(
                "completion_tokens", 0
            ),
            "rubric_prompt_tokens": completion.get("usage", {}).get("prompt_tokens", 0),
            "rubric_score": score,
        }
    return [result]
