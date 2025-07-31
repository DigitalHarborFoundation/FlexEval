"""Completing conversations using LLMs."""

import json
import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from flexeval import classes
from flexeval.configuration import completion_functions
from flexeval.schema.eval_schema import CompletionLlm
from flexeval.schema.evalrun_schema import EvalRun

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


def get_completion(turn: classes.turn.Turn, completion_llm: CompletionLlm):
    completion_function = get_completion_function(completion_llm)
    conversation_history = turn.get_formatted_prompt(
        include_system_prompt=completion_llm.include_system_prompt
    )
    completion = completion_function(
        conversation_history=conversation_history,
        **completion_llm.kwargs,
    )
    return completion


def get_completions(eval_run: EvalRun, evalsetrun: classes.eval_set_run.EvalSetRun):
    n_workers = eval_run.config.max_workers
    if n_workers == 1:
        for thread in evalsetrun.threads:
            # select last turn in thread
            if len(thread.turns) == 0:
                continue
            turn = (
                thread.turns.select()
                .order_by(classes.turn.Turn.index_in_thread.desc())
                .first()
            )
            # TODO handle exceptions appropriately (#58)
            completion = get_completion(turn, eval_run.eval.completion_llm)
            if completion is None:
                continue
            save_completion(completion, turn, evalsetrun, eval_run)
    else:
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures: dict[Future, classes.turn.Turn] = {}
            for thread in evalsetrun.threads:
                if len(thread.turns) == 0:
                    continue
                turn = (
                    thread.turns.select()
                    .order_by(classes.turn.Turn.index_in_thread.desc())
                    .first()
                )
                future = executor.submit(
                    get_completion, turn, eval_run.eval.completion_llm
                )
                futures[future] = turn

            for future in as_completed(futures):
                turn = futures[future]
                completion = future.result()
                if completion is None:
                    continue
                save_completion(completion, turn, evalsetrun, eval_run)


def save_completion(
    completion: dict,
    turn: classes.turn.Turn,
    evalsetrun: classes.eval_set_run.EvalSetRun,
    eval_run: EvalRun,
):
    new_message_completions = completion["choices"]
    if len(new_message_completions) > 1:
        logger.warning(
            "We don't yet support multiple completions, using just the first one."
        )
    new_message_completion = new_message_completions[0]["message"]
    if turn.role == "assistant":
        # don't create a new Turn, because this completion is a continuation of an existing assistant turn
        new_turn = turn
    else:
        new_turn = classes.turn.Turn.create(
            evalsetrun=evalsetrun,
            dataset=turn.dataset,
            thread=turn.thread,
            index_in_thread=turn.index_in_thread + 1,
            role=new_message_completion["role"],
        )
    prev_message = (
        turn.messages.select()
        .order_by(classes.message.Message.index_in_thread.desc())
        .first()
    )
    new_message_context = prev_message.get_context()
    new_message_context.append(
        {"role": prev_message.role, "content": prev_message.content}
    )
    classes.message.Message.create(
        evalsetrun=evalsetrun,
        dataset=turn.dataset,
        thread=turn.thread,
        turn=new_turn,
        index_in_thread=prev_message.index_in_thread + 1,
        role=new_message_completion["role"],
        content=new_message_completion["content"],
        context=json.dumps(new_message_context),
        system_prompt=prev_message.system_prompt,
        is_flexeval_completion=True,
        # TODO I have no idea what model_name is supposed to be, and the completion function name doesn't seem that useful
        model_name=eval_run.eval.completion_llm.function_name,
        prompt_tokens=completion.get("usage", {}).get("prompt_tokens", None),
        completion_tokens=completion.get("usage", {}).get("completion_tokens", None),
    )
    # TODO also save any toolcalls
