import json
import logging
import random as rd
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from flexeval import compute_metrics, run_utils
from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.metric import Metric
from flexeval.classes.turn import Turn
from flexeval.schema import EvalRun, FileDataSource
from flexeval.io.parsers import yaml_parser

logger = logging.getLogger(__name__)


# Levels of abstraction -
# Dataset
# Thread
# Turn
# Message
# ToolCall
# Metric

# Features to add:
# - allow comparison with 'ideal' responses


def run_from_name_args(
    input_data: list[Path],
    database_path: Path,
    eval_name: str,
    config_path: str,
    evals_path: str,
    **kwargs,
):
    data_sources = [FileDataSource(path=input_path) for input_path in input_data]
    config = yaml_parser.load_config_from_yaml(config_path)
    evals = yaml_parser.load_evals_from_yaml(evals_path)
    if eval_name not in evals:
        raise ValueError(
            f"Eval name {eval_name} not in defined evals: {list(evals.keys())}"
        )
    selected_eval = evals[eval_name]
    if selected_eval.name is None or selected_eval.name.strip() == "":
        selected_eval.name = eval_name
    for key, value in kwargs.items():
        setattr(config, key, value)
    eval_run = EvalRun(
        data_sources=data_sources,
        database_path=database_path,
        eval=selected_eval,
        config=config,
    )
    return run(eval_run)


def run(eval_run: EvalRun) -> EvalRunner:
    """Runs the evaluations."""
    runner = EvalRunner(eval_run)

    #######################################################
    ############  Create Test Run  ########################
    #######################################################
    try:
        runner.logger.info("Creating EvalSetRun")
        # TODO instead of raw 'metrics', pass in graph created when setting up the runner

        evalsetrun = run_utils.build_eval_set_run(runner)
        runner.logger.info(f"Metric graph: {evalsetrun.metrics_graph_ordered_list}")
    except Exception:
        runner.logger.exception(
            "An error occurred creating the EvalSetRun.", exc_info=True
        )
        runner.shutdown_logging()
        raise

    #######################################################
    ############  Load and Parse Data  ####################
    #######################################################

    try:
        runner.logger.debug("Loading data")

        # set random seed
        rd_seed = runner.evalrun.config.random_seed_conversation_sampling
        rd.seed(rd_seed)
        runner.logger.info(f"Set random seed to {rd_seed}")

        run_utils.build_datasets(runner, evalsetrun)
    except Exception:
        runner.logger.exception(
            "An error occurred creating dataset metadata.", exc_info=True
        )

    try:
        runner.logger.info("Parsing data files")
        for dataset in evalsetrun.datasets:
            runner.logger.debug(f"Loading data from {dataset.filename}")
            dataset.load_data()
    except Exception:
        runner.logger.exception("An error occurred loading data.", exc_info=True)

    # Do completions, if necessary
    try:
        if evalsetrun.do_completion:
            # We do this by creating new turns
            runner.logger.info("Generating completions")

            # Set up a ThreadPoolExecutor to manage threading
            n_workers = runner.evalrun.config.max_workers
            runner.logger.info(f"Generating completions with {n_workers} workers.")
            if n_workers == 1:
                completions = []
                for turn in evalsetrun.turns:
                    completion = turn.get_completion(
                        include_system_prompt=False  # TODO - pull this from config, maybe from runner.evalrun.eval.completion_llm.include_system_prompt
                    )
                    if completion is not None:
                        completions.append(completion)
            elif n_workers > 1:
                with ThreadPoolExecutor(max_workers=n_workers) as executor:
                    # Submit all turns to the executor
                    futures = [
                        executor.submit(
                            turn.get_completion, include_system_prompt=False
                        )  # TODO - pull this from config, maybe from runner.evalrun.eval.completion_llm.include_system_prompt
                        for turn in evalsetrun.turns
                    ]

                    # Optionally, wait for all futures to complete and handle exceptions
                    for future in as_completed(futures):
                        try:
                            future.result()  # If you need to catch exceptions or ensure completion
                        except Exception:
                            runner.logger.exception(
                                "An error occurred during processing"
                            )
                completions = [
                    future.result() for future in futures if future.result() is not None
                ]

            runner.logger.info("Saving completions to database.")
            for completion in completions:
                # {"choices": [{"message": {"content": "hi", "role": "assistant"}}]}
                for message in completion:
                    assert isinstance(message["turn"], list)
                    Turn.create(
                        evalsetrun=message["evalsetrun"],
                        dataset=message["dataset"],
                        datasetrow=message["datasetrow"],
                        turn_number=message["turn_number"],
                        turn=json.dumps(message["turn"]),
                        role=message["role"],
                        content="\n".join(
                            [i.get("content", "") for i in message["turn"]]
                        ),
                        tool_used=message["tool_used"],
                        system_prompt=message["system_prompt"],
                        context=json.dumps(message["context"]),
                        is_final_turn_in_input=message["is_final_turn_in_input"],
                        is_completion=True,
                        prompt_tokens=message["prompt_tokens"],
                        completion_tokens=message["completion_tokens"],
                    )

    except Exception:
        runner.logger.exception(
            "An error occurred generating completions.", exc_info=True
        )
        if eval_run.config.raise_on_completion_error:
            runner.shutdown_logging()
            raise

    #######################################################
    #################  Compute Metrics  ###################
    #######################################################

    try:
        # Set up a ThreadPoolExecutor to manage threading
        n_workers = runner.evalrun.config.max_workers
        runner.logger.info(f"Generating metrics with {n_workers} workers.")

        # collect turns to run metrics on
        turns_to_evaluate = []
        for turn in evalsetrun.turns:
            # only do completions
            if (
                evalsetrun.do_completion and turn.is_completion
            ):  # NOTE: ANR: turn no longer has an is_completion
                turns_to_evaluate.append(turn)
            # or do all turns
            elif not evalsetrun.do_completion:
                turns_to_evaluate.append(turn)

        # collect function calls to make
        # here, we'll use the metric ordering established in evalsetrun.metric_graph
        rubric_count = 0
        # Here, need loops over threads, turns, messages, and tool calls, and then getting the appropriate
        # metrics to each. Seems like we can still use the same metric_graph (which may have ≥ 4 connected
        # components), and enforce in validation step that dependencies are only between metrics defined
        # at the same granularity.
        # Create a dictionary for the metrics
        metrics_by_level = {}
        for metric_instance in json.loads(evalsetrun.metrics_graph_ordered_list):
            metric_level = metric_instance["metric_level"]
            if metric_level not in metrics_by_level:
                metrics_by_level[metric_level] = []
            metrics_by_level[metric_level].append(metric_instance)
        # TODO: if we go back to supporting completions, this will likely need to change
        threads_to_evaluate = [thread for thread in evalsetrun.threads]
        messages_to_evaluate = [message for message in evalsetrun.messages]
        toolcalls_to_evaluate = [toolcall for toolcall in evalsetrun.toolcalls]
        object_lists_by_level = {
            "Thread": threads_to_evaluate,
            "Turn": turns_to_evaluate,
            "Message": messages_to_evaluate,
            "ToolCall": toolcalls_to_evaluate,
        }
        # log details of the identified metrics and objects at the various levels
        for level, object_list in object_lists_by_level.items():
            metrics_at_level = metrics_by_level.get(level, [])
            metric_names = ", ".join(
                [
                    f"{metric['evaluation_name']} ({metric['id']})"
                    for metric in metrics_at_level
                ]
            )
            runner.logger.debug(
                f"Will execute {len(metrics_at_level)} metrics for {len(object_list)} objects at the {level} level: {metric_names}"
            )

        for level, object_list in object_lists_by_level.items():
            # Add the metrics to objects at this level
            metrics_at_level = metrics_by_level.get(level, [])
            compute_metrics.add_all_metrics_to_objects(object_list, metrics_at_level)
            # Update the count of how many rubrics might be run based on rubric evals at this level
            rubric_count += compute_metrics.count_rubric_metrics(object_list)

        runner.logger.info(
            f"Metrics will include up to {rubric_count} rubric evaluations."
        )
        metric_computer = runner.get_metric_computer()
        if n_workers == 1:
            metrics = []
            for level, object_list in object_lists_by_level.items():
                runner.logger.info(
                    f"Computing metrics for level {level} on {len(object_list)} objects."
                )
                for object in object_list:
                    cur_metrics = metric_computer.compute_metrics(object)
                    for m in cur_metrics:
                        if m.get("evaluation_type", None) is None:
                            runner.logger.exception(
                                f"Metric {m} does not have a value for the key `type`."
                            )
                            if eval_run.config.raise_on_metric_error:
                                raise ValueError(
                                    f"Metric {m} does not have a value for the key `type`."
                                )
                        if m.get("metric_value", None) is None:
                            runner.logger.exception(
                                f"Metric {m} does not have a value for the key `metric_value`."
                            )
                            if eval_run.config.raise_on_metric_error:
                                raise ValueError(
                                    f"Metric {m} does not have a value for the key `metric_value`."
                                )
                    metrics.extend(cur_metrics)

        else:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = []
                for level, object_list in object_lists_by_level.items():
                    for object in object_list:
                        futures.append(
                            executor.submit(metric_computer.compute_metrics, object)
                        )

                # Wait for all futures to complete and handle exceptions
                for fid, future in enumerate(futures):
                    try:
                        future.result()  # If you need to catch exceptions or ensure completion
                        if fid % 100 == 0:
                            runner.logger.info(
                                f"Metrics futures resulted: {fid} / {len(futures)}"
                            )
                    except Exception:
                        runner.logger.exception("An error occurred during processing")
                metrics = []
                for future in futures:
                    metrics += future.result()

        runner.logger.info(f"Saving {len(metrics)} metrics to database.")
        for metric in metrics:
            # TODO - speed this up somehow
            thread = metric.get("thread")
            if thread is None:
                thread = metric[metric["metric_level"].lower()].thread
            Metric.create(
                message=metric.get("message", None),
                turn=metric.get("turn", None),
                toolcall=metric.get("toolcall", None),
                evalsetrun=metric[
                    metric["metric_level"].lower()
                ].evalsetrun,  # metric["turn"].evalsetrun,
                dataset=metric[
                    metric["metric_level"].lower()
                ].dataset,  # metric["turn"].dataset,
                thread=thread,
                evaluation_name=metric["evaluation_name"],
                evaluation_type=metric["evaluation_type"],
                metric_name=metric["metric_name"],
                metric_value=metric["metric_value"],
                metric_level=metric["metric_level"],
                kwargs=metric["kwargs"],
                depends_on=json.dumps(metric["depends_on"]),
                context_only=metric.get("context_only", False),
                source=metric["source"],
                rubric_prompt=metric.get("rubric_prompt", None),
                rubric_completion=metric.get("rubric_completion", None),
                rubric_model=metric.get("rubric_model", None),
                rubric_completion_tokens=metric.get("rubric_completion_tokens", None),
                rubric_prompt_tokens=metric.get("rubric_prompt_tokens", None),
                rubric_score=metric.get("rubric_score", None),
            )

    except Exception:
        runner.logger.exception("An error occurred computing metrics.", exc_info=True)
        if eval_run.config.raise_on_metric_error:
            runner.shutdown_logging()
            raise

    runner.logger.info("Evaluation run complete.")
    runner.shutdown_logging()
    return runner
