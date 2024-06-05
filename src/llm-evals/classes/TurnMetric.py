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

from configuration import function_metrics
from configuration import completion_functions


class TurnMetric(BaseModel):
    """Holds a single metric/property computed based one just ONE turn"""

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="turnproperties")
    dataset = pw.ForeignKeyField(Dataset, backref="turnproperties")
    datasetrow = pw.ForeignKeyField(DatasetRow, backref="turnproperties")
    turn = pw.ForeignKeyField(Turn, backref="turnproperties")

    definition = pw.TextField()
    function_name = pw.TextField()
    name = pw.TextField()
    value = pw.FloatField(null=True)  # necessary if rubric result is INVALID
    kwargs = pw.TextField()
    source = pw.TextField()
    type = pw.TextField()
    rubric_completion = pw.TextField(null=True)
    rubric_model = pw.TextField(null=True)
    rubric_completion_tokens = pw.IntegerField(null=True)
    rubric_prompt_tokens = pw.IntegerField(null=True)
    rubric_score = pw.TextField(null=True)


def compute_metric(
    metric_name: str, metric_definition: dict, turn: Turn, metric_type: str
) -> list:

    if metric_type == "function":
        metrics = compute_function_metric(
            metric_name=metric_name, metric_definition=metric_definition, turn=turn
        )
    elif metric_type == "rubric":
        metrics = compute_rubric_metric(
            metric_name=metric_name, metric_definition=metric_definition, turn=turn
        )
    else:
        raise Exception(
            f"The argument metric_type provided to compute_metric is invalid. Must be one of `function` or `rubric`. You passed `{metric_type}`."
        )
    return metrics


def compute_function_metric(metric_name: str, metric_definition: dict, turn: Turn):
    # this is NOT a method - it's a function b/c we want it to be able to return multiple metrics, if more than one is returned
    # they share most of the same information though so it's convenient to have them constructed similarly
    # will return a list of dictionaries
    metric_kwargs = metric_definition.get("kwargs", {})

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
            "definition": metric_definition,
            "function_name": metric_name,
            "kwargs": metric_kwargs,
            "source": metric_source,
            "type": "function",
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


def compute_rubric_metric(metric_name: str, metric_definition: dict, turn: Turn):

    # load metrics
    rubrics = json.loads(turn.evalsetrun.rubrics)
    assert (
        metric_name in rubrics
    ), f"You requested a rubric called `{metric_name}`, but only these were found:{rubrics.keys()}."

    metric_kwargs = metric_definition.get("kwargs", {})

    prompt = rubrics.get(metric_name).get("prompt", "")

    # # if do_completion is False,
    # if "{completion}" in prompt and not turn.is_completion:
    #     raise Exception(
    #         f'The specified metric {metric_name} requires a completion to be completed, but you set "do_completion" to False (or missing) in the evals.yaml file.'
    #     )

    # format input for rubric
    conversation, context, completion = turn.format_input_for_rubric()

    # TODO possibly -- make "format_input_for_rubric" return just a single turn at a given lag???? or a range?

    # assistant: what's up
    # user: i need help with a problem
    # assistant: ok what problem
    # user: what does a parabola look like?
    # assistant: it's curvy

    # assistant: what's up
    # user: i need help with a problem
    # assistant: ok what problem
    # user: I need to find the roots of a parabola
    # assistant: here's a graph of a parabola <graph> the roots are where it crosses the x-axis

    # Q: is this tool call a response to a student request for a plot?
    # given that it's a tool call, what proportion of PREVIOUS adjacent user turns are requests for a plot?

    # We need to know: is the previous user turn (or N turns) a request for a plot?

    # TAKEAWAY: to evaluate this question on THIS turn, we need to evaluate a rubric on a PREVIOUS turn or turns

    # Q: when a student requests a plot, does the tutor oblige?
    # This one would requre EVERY student turn to be evaluated?

    # Can we distinguish these somehow?

    # student: draw a plot
    # tutor: no let's talk about the problem
    # student: do it now
    # tutor: here's a plot <plot>

    # A, B
    # p(B=T|A=T) <- allows us to filter out A=F b/c we don't care

    # but we could also compute counts for B=T, B=F, A=T, A=F and then do queries after the fact

    # given that it's a tool call, what proportion of PREVIOUS adjacent user turns are requests for a plot?

    # TODO - re-think how these are separated - sometimes we want to analyze non-completed conversations
    # as if they were completions

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
    # if "{turn}" in prompt:
    #     assert (
    #         "{context}" not in prompt
    #     ), f"Your rubric {metric_name} is evaluating the current {{turn}}, and cannot have other parts of the convsersation. If you want to evaluate a completion, use {{context}} and {{completion}} placeholders."
    #     assert (
    #         "{completion}" not in prompt
    #     ), f"Your rubric {metric_name} is evaluating the current {{turn}}, and cannot have other parts of the convsersation. If you want to evaluate a completion, use {{context}} and {{completion}} placeholders."
    # if "{context}" in prompt and "{completion}" not in prompt:
    #     raise Exception(
    #         f"Your rubric {metric_name} has {{context}} but no {{completion}}. Please add a {{completion}} entry. If you just want to evaluate a single turn, use {{turn}}"
    #     )
    # if "{completion}" in prompt and "{context}" not in prompt:
    #     raise Exception(
    #         f"Your rubric {metric_name} has {{completion}} but no {{context}}. Please add a {{context}} entry. If you just want to evaluate a single turn, use {{turn}}"
    #     )

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

    # if isinstance(rubrics.get(metric_name).get("choice_strings", None), str):
    #     choice_strings = rubrics.get(metric_name).get("choice_strings").split()
    # elif isinstance(rubrics.get(metric_name).get("choice_strings", None), list):
    #     choice_strings = rubrics.get(metric_name).get("choice_strings")
    choice_scores = rubrics.get(metric_name).get("choice_scores")
    # get rubric grader
    # TODO - this would be the rubric LLM
    completion_function = json.loads(turn.evalsetrun.completion_llm)
    completion_fn_name = completion_function.get("function_name", None)
    completion_fn_kwargs = completion_function.get("kwargs", {})
    if hasattr(completion_functions, completion_fn_name) and hasattr(
        completion_functions, completion_fn_name
    ):
        completion_function = getattr(completion_functions, completion_fn_name, None)
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
            **completion_fn_kwargs,
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
            "definition": metric_definition,
            "function_name": metric_name,
            "kwargs": metric_kwargs,
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
