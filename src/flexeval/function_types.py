"""Inspection utilities that use type hints to determine the appropriate object to pass to a function metric.

See :mod:`~flexeval.schema.eval_schema`.
"""

import inspect
import logging
import types
import typing
from collections.abc import Callable, Iterable

from flexeval.classes import message, thread, tool_call, turn
from flexeval.schema import eval_schema

AnyFunctionObjectInput = typing.Union[
    turn.Turn,
    message.Message,
    thread.Thread,
    tool_call.ToolCall,
]
FLEXEVAL_TYPE_SET: set[type] = {
    turn.Turn,
    message.Message,
    thread.Thread,
    tool_call.ToolCall,
}

logger = logging.getLogger(__name__)


def is_callable_valid_for_metric_level(
    metric_function: Callable, metric_level: eval_schema.MetricLevel
) -> bool:
    valid_levels = get_valid_levels_for_callable(metric_function)
    return metric_level in valid_levels


def get_valid_levels_for_callable(metric_function: Callable) -> set[str]:
    """Given a callable, determine the valid metric_level values based on the type annotation of the first parameter.

    Args:
        metric_function (Callable): A callable, probably one available via EvalRun

    Returns:
        set[str]: Valid values for MetricItem.metric_level
    """
    accepted_parameter_types = get_first_parameter_types(metric_function)
    valid_levels = set()
    for flexeval_type in FLEXEVAL_TYPE_SET:
        if flexeval_type in accepted_parameter_types:
            valid_levels.add(flexeval_type.__name__)
    if str in accepted_parameter_types:
        for level in ["Message", "Turn", "Thread"]:
            valid_levels.add(level)
    if list in accepted_parameter_types:
        for level in ["Turn", "Thread"]:
            valid_levels.add(level)
    if dict in accepted_parameter_types:
        valid_levels.add("ToolCall")
    return valid_levels


def get_first_parameter_types(metric_function: Callable) -> set[type]:
    input_type = next(
        iter(inspect.signature(metric_function).parameters.values())
    ).annotation
    if input_type is inspect._empty:
        logger.debug(
            f"Function '{metric_function}' has a first parameter with no type annotation."
        )
        return set()
    return get_acceptable_arg_types(input_type)


def get_acceptable_arg_types(input_type: type) -> set[type]:
    # Note: we don't support NewType annotations yet
    origin_type = typing.get_origin(input_type)
    if origin_type is typing.Annotated:
        # unpack Annotated types
        input_type = typing.get_args(input_type)[0]
        origin_type = typing.get_origin(input_type)
    if origin_type in (typing.Union, types.UnionType):
        union_arg_type_sets = [
            get_acceptable_arg_types(type_arg)
            for type_arg in typing.get_args(input_type)
        ]
        return set.union(*union_arg_type_sets)
    else:  # not a union type
        if origin_type is not None:
            # e.g. input_type=list[str], origin_type=list
            return {origin_type}
        else:
            # e.g. input_type=list, origin_type=list
            if input_type is list or input_type is Iterable:
                logger.warning(
                    "Type hint {input_type} lacks the detail that would allow us to determine the specific objects it accepts."
                )
            return {input_type}


def get_function_input(
    metric_function: Callable,
    metric_level: eval_schema.MetricLevel,
    input_object: AnyFunctionObjectInput,
    context_only: bool,
) -> AnyFunctionObjectInput | str | dict | list:
    """Coerce input_object to a type accepted by metric_function at this metric_level.

    Args:
        metric_function (Callable): Function to invoke with the returned input.
        metric_level (eval_schema.MetricLevel): The metric level at which metric_function is being invoked.
        input_object (AnyFunctionObjectInput): The input_object to be coerced, or passed as-is if accepted by metric_function.
        context_only (bool): Determines how strings and lists are converted. See schema documentation.

    Raises:
        ValueError: If the function accepts at least one declared type, but
        it's a type we don't support at all e.g. set or
        it's a type we don't support at this metric_level.

    Returns:
        AnyFunctionObjectInput | str | dict | list: The coerced input for metric_function.
    """
    if metric_level not in eval_schema.VALID_METRIC_LEVELS:
        raise ValueError(
            f"metric_level '{metric_level}' not one of the valid levels: {eval_schema.VALID_METRIC_LEVELS}"
        )
    input_type = type(input_object)
    accepted_parameter_types = get_first_parameter_types(metric_function)
    if len(accepted_parameter_types) == 0:
        logger.debug(
            f"Metric function '{metric_function}' has a first parameter with no type hint, so we can't determine if a type transformation needs to be applied."
        )
        return input_object
    if input_type in accepted_parameter_types:
        # no transformation necessary; the function accepts the type we already have
        return input_object
    elif dict in accepted_parameter_types and metric_level == "ToolCall":
        return input_object.get_dict_representation()
    elif list in accepted_parameter_types and metric_level in ["Turn", "Thread"]:
        if context_only:
            return input_object.get_context()
        else:
            # this is on a single turn - pass in the parsed list
            return input_object.get_content()
    elif str in accepted_parameter_types:
        if metric_level == "ToolCall":
            raise ValueError(
                "Functions that accept strings can't be used for tool calls. Accept a dict (or a flexeval.classes.tool_call.ToolCall) instead."
            )
        if context_only:
            # join together all previous turns
            return join_all_contents_to_string(input_object.get_context())
        else:
            # current turn only
            return join_all_contents_to_string(input_object.get_content())
    else:
        # the function accepts at least one declared type, but either:
        # - it's a type we don't support at all e.g. set
        # - it's a type we don't support at this metric_level
        raise ValueError(
            f"For metric level '{metric_level}', can't coerce '{input_type.__name__}' for function '{metric_function}' to accepted parameter type(s) '{', '.join([type.__name__ for type in accepted_parameter_types])}'."
        )


def join_all_contents_to_string(content: list[dict] | typing.Any) -> str:
    """
    content is a list of dictionaries whose keys include 'content'.
    Returns a string with all the 'content' entries concatenated together,
    separated by newline.
    """
    if isinstance(content, list):
        content = "\n".join([item.get("content", "") for item in content])
    return content
