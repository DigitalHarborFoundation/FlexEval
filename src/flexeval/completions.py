"""Completing conversations using LLMs."""

import logging
from collections.abc import Callable

from flexeval.schema.evalrun_schema import EvalRun
from flexeval.schema.eval_schema import CompletionLlm
from flexeval.classes.turn import Turn
from flexeval.classes.eval_set_run import EvalSetRun

from flexeval.configuration import completion_functions


logger = logging.getLogger(__name__)


def get_completion_function(completion_llm: CompletionLlm) -> Callable:
    """Identify a completion function given the completion LLM configuration.

    Args:
        completion_llm (CompletionLlm): The description of the function to retrieve.

    Raises:
        ValueError: If not found in :mod:`~flexeval.configuration.completion_functions` or in globals by function_name.

    Returns:
        Callable: The completion function.
    """
    # Check if the function name exists in the global namespace and call it
    if hasattr(completion_functions, completion_llm.function_name):
        completion_function = getattr(
            completion_functions, completion_llm.function_name
        )
        return completion_function
    if completion_llm.function_name in globals() and callable(
        globals()[completion_llm.function_name]
    ):
        # TODO probably don't allow this by default, and also offer a way to specify other places where completion_functions can live.
        logger.debug("Found function in globals(), which could be trouble.")
        return globals()[completion_llm.function_name]
    else:
        raise ValueError(
            "No completion function named " + completion_llm.function_name + " found."
        )


def get_completion(turn: Turn, completion_llm: CompletionLlm):
    completion_function = get_completion_function(completion_llm)
    conversation_history = turn.get_formatted_prompt(
        include_system_prompt=completion_llm.include_system_prompt
    )
    completion = completion_function(
        conversation_history=conversation_history,
        **completion_llm.kwargs,
    )
    return completion


def get_completions(eval_run: EvalRun, evalsetrun: EvalSetRun):
    n_workers = eval_run.config.max_workers
    completions = []
    for turn in evalsetrun.turns:
        completion = get_completion(turn, eval_run.eval.completion_llm)
        if completion is not None:
            completions.append(completion)
