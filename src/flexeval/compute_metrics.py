import copy
import inspect
import json
import string
from typing import Union, Any

from flexeval.classes.message import Message
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn
from flexeval.configuration import completion_functions, function_metrics


class MetricComputer:
    def __init__(self, function_modules: list, include_default_functions: bool = True):
        self.function_modules = function_modules
        if include_default_functions:
            self.function_modules.append(function_metrics)

    def compute_metrics(self, object: Union[Thread, Turn, Message, ToolCall]):
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
        # we'll keep the results in a list
        # for each new metric, if it has dependencies, we'll need to make sure they're met - otherwise we won't run it
        evaluated_metrics = []
        # METRICS IN ORDER
        for metric_to_evaluate in object.metrics_to_evaluate:
            # see if there's a dependency
            dependencies_are_all_met = True
            # If there are no dependencies, this loop won't execute
            # and the metric will be evaluated
            if len(metric_to_evaluate.get("depends_on")) > 0:
                # here, we have a metric with 1+ dependencies
                # ALL of these dependencies must be satisfied

                # we determine whether a given metric is a match if it matches
                # 1 - the id
                # 2 - the metric_name
                # 3 - the metric_min_value
                # 4 - the metric_max_value
                # not meeting ANY of them will short-circuit the loop and cause the eval to not evaluate
                # check all dependencies
                for dependency in metric_to_evaluate.get("depends_on"):
                    # for each dependency, assume it's not met
                    # if it's in the list AND its values meet the criteria, it's met
                    dependency_is_met = False
                    # if a specific metric_name was specified, you need to match exactly:
                    if "metric_name" in dependency:
                        for em in evaluated_metrics:
                            # I think the 'depends_on' should have all fields populated at this point

                            if (
                                em["id"] == dependency["parent_id"]
                                and em["metric_name"] == dependency["metric_name"]
                                and em["metric_value"] >= dependency["metric_min_value"]
                                and em["metric_value"] <= dependency["metric_max_value"]
                            ):
                                # this specific dependency was met - can quit looking
                                dependency_is_met = True
                                break
                    else:
                        # if no specific metric_name was specified, you just need to match ANY metric_name
                        # on the other criteria
                        for em in evaluated_metrics:
                            # print("em", em)
                            # print("dependency", dependency)
                            # I think the 'depends_on' should have all fields populated at this point
                            if (
                                em["id"] == dependency["parent_id"]
                                # and em["metric_name"] == dependency["metric_name"]
                                and em["metric_value"] >= dependency["metric_min_value"]
                                and em["metric_value"] <= dependency["metric_max_value"]
                            ):
                                # this specific dependency was met - can quit looking
                                dependency_is_met = True
                                break
                    if not dependency_is_met:
                        dependencies_are_all_met = False
                        # if even one dependency is not met - don't do the evaluation
                        break
            if dependencies_are_all_met:
                # pass through arguments, but add 'self' as the turn
                # ONLY call if dependencies are ALL met
                # TODO - maybe in the future we'll want to add the computed value from
                # the dependency through as an argument here
                evaluated_metrics += self.compute_metric(object, **metric_to_evaluate)
            else:
                pass
                # print(f"\nNot runing metric because dependency was not met:")
                # print(metric_to_evaluate)
        return evaluated_metrics

    def compute_metric(
        self,
        object: Union[Thread, Turn, Message, ToolCall],
        evaluation_name: str,
        evaluation_type: str,
        metric_level: str,
        kwargs: dict,
        context_only: bool = None,
        last_instance_only: bool = None,
        depends_on: list = None,
        id: int = None,
        notes: str = None,  # just a placeholder
    ) -> list:
        if evaluation_type == "function":
            metrics = self.compute_function_metric(
                function_name=evaluation_name,
                metric_kwargs=kwargs,
                metric_level=metric_level,
                context_only=context_only,
                last_turn_only=last_instance_only,
                input_object=object,
                depends_on=depends_on,
                id=id,
            )
        elif evaluation_type == "rubric":
            metrics = self.compute_rubric_metric(
                rubric_name=evaluation_name,
                metric_kwargs=kwargs,
                metric_level=metric_level,
                object=object,
                depends_on=depends_on,
                id=id,
            )
        else:
            raise Exception(
                f"The argument evaluation_type provided to compute_metric is invalid. Must be one of `function` or `rubric`. You passed `{type}`."
            )
        return metrics

    def invoke_function(
        self, metric_function: callable, input_object, metric_kwargs, context_only: bool
    ):
        # TODO: Confirm that this verification is happening in verify installation instead.

        # This gets the type of the first argument of the function
        input_type = next(
            iter(inspect.signature(metric_function).parameters.values())
        ).annotation
        # Check whether the metric_function has a string or a list input as the first thing.
        # If so, need to extract the content first.
        if input_type is str:
            # This should apply only for Message, Turn, or Thread types.
            # For Turn and Thread, concatenates all together
            input = None
            if context_only:
                # join together the string contents of all previous turns
                input = join_all_contents_to_string(input_object.get_context())
            else:
                # current turn only
                input = join_all_contents_to_string(input_object.get_content())
            metrics_result = metric_function(input, **metric_kwargs)
        elif input_type is list:
            # This should apply for the Turn and Thread types only
            if context_only:
                metrics_result = metric_function(
                    input_object.get_context(), **metric_kwargs
                )
            else:
                # this is on a single turn - pass in the parsed list
                metrics_result = metric_function(
                    input_object.get_content(), **metric_kwargs
                )
        elif input_type is dict:
            # This should apply for the ToolCall type only
            metrics_result = metric_function(
                input_object.get_dict_representation(), **metric_kwargs
            )
        else:
            # Must be a Thread/Turn/Message/ToolCall [verified in validation of setup]
            metrics_result = metric_function(input_object, **metric_kwargs)

        return metrics_result

    def find_function(self, function_name: str):
        for function_module in self.function_modules:
            if hasattr(function_module, function_name) and callable(
                getattr(function_module, function_name)
            ):
                metric_function = getattr(function_module, function_name)
                metric_source = inspect.getsource(metric_function)
                return metric_function, metric_source
        raise ValueError(
            f"Metric function with name `{function_name}` was not found in any of the {len(self.function_modules)} provided function modules."
        )

    def compute_function_metric(
        self,
        function_name: str,
        metric_kwargs: dict,
        input_object: Union[Thread, Turn, Message, ToolCall],
        metric_level: str,
        context_only: bool,
        last_turn_only: bool,
        depends_on: list,
        id: int,
    ):
        # this is NOT a method - it's a function b/c we want it to be able to return multiple metrics, if more than one is returned
        # they share most of the same information though so it's convenient to have them constructed similarly
        # will return a list of dictionaries

        # if this is set, exit unless the criteria are met
        if last_turn_only and not (
            input_object.is_completion or input_object.is_final_turn_in_input
        ):
            return []
        # Check if the function exists in any of the function namespaces
        metric_function, metric_source = self.find_function(function_name)
        metrics_result = self.invoke_function(
            metric_function, input_object, metric_kwargs, context_only
        )

        base_result = {
            metric_level.lower(): input_object,
            "evaluation_name": function_name,
            "evaluation_type": "function",
            "metric_level": metric_level,
            "kwargs": metric_kwargs,
            "source": metric_source,  # TODO - put this back?
            "context_only": context_only,
            "last_turn_only": last_turn_only,
            "depends_on": depends_on,
            "id": id,
        }
        # now deal with output
        if isinstance(metrics_result, float) or isinstance(metrics_result, int):
            result = copy.deepcopy(base_result)
            result["metric_name"] = function_name
            result["metric_value"] = metrics_result
            return [result]
        elif isinstance(metrics_result, dict):
            result_list = []
            for k, v in metrics_result.items():
                result = copy.deepcopy(base_result)
                result["metric_name"] = k
                result["metric_value"] = float(v)
                result_list.append(result)
            return result_list
        elif isinstance(metrics_result, list):
            result_list = []

            for entry in metrics_result:
                # print(function_name, entry)
                result = copy.deepcopy(base_result)
                result["metric_name"] = entry.get("name", None)
                result["metric_value"] = float(entry.get("value", None))
                result_list.append(result)
            return result_list
        else:
            raise Exception(
                f"The metric type returned from `{metric_function}` is not a supported type. It must be one of `list`, `int`, `float`, or `dict`. You supplied `{type(metrics_result)}`."
            )

    def compute_rubric_metric(
        self,
        rubric_name: str,
        metric_kwargs: dict,
        object: Union[Thread, Turn, Message],
        metric_level: str,
        depends_on: list,
        id: int,
    ):
        # load metrics
        rubrics = json.loads(object.evalsetrun.rubrics)
        assert (
            rubric_name in rubrics
        ), f"You requested a rubric called `{rubric_name}`, but only these were found:{rubrics.keys()}."

        prompt = rubrics.get(rubric_name).get("prompt", "")

        # format input for rubric
        conversation, context, content, tool_calls = object.format_input_for_rubric()
        # conversation : all turns; context: all turns without the last entry; completion: only the last entry
        # use three keywords:
        # #{conversation} -- The whole conversation
        # #{context} -- The previous turns without the current entry
        # #{content} -- Only the current turn / message / toolcall depending on the metric_level
        # for the future: add {compeltion} under the condition of do_completion == True

        # Add verfication steps before populating the rubric
        # case 1: {conversation} and {context} should not go together
        # case 2: {completion} and {content} should not go together
        # case 3: if there is a {completion}, do_completion should be true

        if "{conversation}" in prompt and "{context}" in prompt:
            raise Exception(
                "Your rubric should not have both {conversation} and {context}. Please check the README file for more information about how to write FlexEval rubrics."
            )

        if "{completion}" in prompt and "{content}" in prompt:
            raise Exception(
                "Your rubric should not have both {content} and {completion}. Please check the README file for more information about how to write FlexEval rubrics."
            )

        if "{completion}" in prompt and not object.evalsetrun.do_completion:
            raise Exception(
                "Your rubric has {completion}, but in your test specification for this rubric evaluation, do_completion is not True. Please check the README file for more information about how to write FlexEval rubrics."
            )

        populated_prompt = prompt.format(
            conversation=conversation,
            context=context,
            content=content,
            tool_calls=tool_calls,
        )

        # with do_completion == True, only the completion is evaluated with or without the context.
        if object.evalsetrun.do_completion and object.is_completion:
            populated_prompt = prompt.format(completion=content)

        choice_scores = rubrics.get(rubric_name).get("choice_scores")

        # get rubric grader
        grader_completion_function = json.loads(object.evalsetrun.grader_llm)
        grader_completion_fn_name = grader_completion_function.get(
            "function_name", None
        )
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
            # This is the call to the grader completion function!
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

            score = get_match(
                completion_text=completion_text, choice_scores=choice_scores
            )
            result = {
                metric_level.lower(): object,
                "metric_name": rubric_name,
                "evaluation_name": rubric_name,
                "evaluation_type": "rubric",
                "id": id,
                "kwargs": metric_kwargs,
                "depends_on": depends_on,
                "source": populated_prompt,
                "metric_level": metric_level,
                "metric_value": choice_scores[score],
                "rubric_prompt": populated_prompt,
                "rubric_completion": completion_text,
                "rubric_model": completion.get("model", None),
                "rubric_completion_tokens": completion.get("usage", {}).get(
                    "completion_tokens", 0
                ),
                "rubric_prompt_tokens": completion.get("usage", {}).get(
                    "prompt_tokens", 0
                ),
                "rubric_score": score,
            }
        return [result]


def add_all_metrics_to_objects(iterable_of_objects, metrics):
    """
    Adds all metric instances in metrics_for_level to each instance of
    an evaluable object (e.g., Turn, Thread, Message, or ToolCall) in
    iterable_of_objects. This addition is done by appending to the
    `metrics_to_evaluate` field, which all instances in iterable_of_objects
    should have.

    :param iterable_of_objects: list of objects that have a metrics_to_evaluate field
    :param metrics: list of metric instances to add to each object
    """
    for object in iterable_of_objects:
        # Field metrics_to_evaluate initialized in constructor
        # metric dependencies happen WITHIN turns, rather than across
        # this means I can associate a sequence of metrics within each turn
        # but then have the turns execute them in parallel
        # each turn will keep track of its own set of metrics
        # Keeping this as a loop to do the rubric_count appropriately
        object.metrics_to_evaluate = object.metrics_to_evaluate + metrics


def count_rubric_metrics(iterable_of_objects):
    """
    Returns the total number of rubric type metrics in
    the metrics_to_evaluate field in each object.

    :param iterable_of_objects: list of objects that have a metrics_to_evaluate field
    """
    rubric_count = 0
    for object in iterable_of_objects:
        for metric_instance in object.metrics_to_evaluate:
            if metric_instance.get("evaluation_type") == "rubric":
                rubric_count += 1
    return rubric_count


def join_all_contents_to_string(content: list[dict] | Any) -> str:
    """
    content is a list of dictionaries whose keys include 'content'.
    Returns a string with all the 'content' entries concatenated together,
    separated by newline.
    """
    if isinstance(content, list):
        content = "\n".join([item.get("content", "") for item in content])
    return content
