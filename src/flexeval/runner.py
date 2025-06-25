import json
import logging
import random as rd
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from flexeval import compute_metrics, run_utils
from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.turn import Turn
import flexeval.metrics
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
        metrics = compute_metrics.compute_metrics(eval_run, evalsetrun)
        runner.logger.info(f"Saving {len(metrics)} metrics to database.")
        flexeval.metrics.save.save_metrics(metrics)
    except Exception:
        runner.logger.exception("An error occurred computing metrics.", exc_info=True)
        if eval_run.config.raise_on_metric_error:
            runner.shutdown_logging()
            raise

    runner.logger.info("Evaluation run complete.")
    runner.shutdown_logging()
    return runner
