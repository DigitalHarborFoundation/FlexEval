import argparse
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

import json
from classes.EvalRunner import EvalRunner
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.Conversation import Conversation
from classes.Turn import Turn
from classes.TurnEntry import TurnEntry
from classes.TurnMetric import TurnMetric
import dotenv


# Features to add:
# - allow comparison with 'ideal' responses


def run(eval_name: str, evals_path: str, config_path: str):
    """Runs the evaluations.
    We want this to be callable by both the CLI and the webapp
    That means it needs to do argument parsing BEFORE this is called

    TODO - for webapp, config should be an argument here ^
    """
    # TODO - make evals.yaml file path configurable
    runner = EvalRunner(
        eval_name=eval_name,
        config_path=config_path,
        evals_path=evals_path,
    )
    dotenv.load_dotenv(runner.configuration["env_file"])

    with open(runner.configuration["rubric_metrics_path"]) as file:
        rubrics = yaml.safe_load(file)

    #######################################################
    ############  Create Test Run  ########################
    #######################################################
    try:
        runner.logger.info("Creating EvalSetRun")
        # (runner.eval.get("metrics"))
        # TODO instead of raw 'metrics', pass in graph created when setting up the runner

        evalsetrun = EvalSetRun.create(
            name=runner.eval.get("name", ""),
            notes=runner.eval.get("notes", ""),
            metrics=json.dumps(runner.eval.get("metrics", "")),
            metrics_graph_ordered_list=json.dumps(runner.metrics_graph_ordered_list),
            dataset_files=json.dumps(runner.eval.get("data", "")),
            do_completion=runner.eval.get("do_completion", False),
            completion_llm=json.dumps(runner.eval.get("completion_llm", None)),
            model_name=json.dumps(
                runner.eval.get("completion_llm", {}).get("model_name", None)
            ),
            grader_llm=json.dumps(runner.eval.get("grader_llm", None)),
            rubrics=json.dumps(rubrics),
        )
        runner.logger.info(evalsetrun.metrics_graph_ordered_list)
    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)
        raise e

    #######################################################
    ############  Load and Parse Data  ####################
    #######################################################

    try:
        runner.logger.info("Loading data")
        for filename in evalsetrun.get_datasets():
            # these will automatically be saved as a property of evalsetrun
            Dataset.create(evalsetrun=evalsetrun, filename=filename)

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    try:
        runner.logger.info("Parsing data files")
        for dataset in evalsetrun.datasets:
            runner.logger.debug(f"Loading data from {dataset.filename}")
            rows = dataset.load_data()
            for row in rows:
                Conversation.create(
                    dataset=dataset,
                    evalsetrun=dataset.evalsetrun,
                    input=json.dumps(row.get("input", None)),
                    ideals=json.dumps(row.get("ideals", None)),
                )
    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    try:
        runner.logger.info("Parsing turns")
        for dataset in evalsetrun.datasets:
            for conversation in dataset.conversation:
                conversation.tally_tokens()
                # turns is a list of dictionaries
                turns = conversation.get_turn_components()
                for turn_ix, turn in enumerate(turns):
                    assert isinstance(turn["turn"], list)
                    TurnComponent.create(
                        evalsetrun=row.evalsetrun,
                        dataset=dataset,
                        datasetrow=row,
                        turn_number=turn_ix + 1,
                        turn=json.dumps(turn["turn"]),
                        role=turn["role"],
                        content=content,
                        tool_used=turn["tool_used"],
                        system_prompt=turn["system_prompt"],
                        context=json.dumps(
                            [item for d in turns[:turn_ix] for item in d["turn"]]
                        ),  # concatenate all turns except the current
                        is_final_turn_in_input=turn["is_final_turn_in_input"],
                        is_completion=False,
                        prompt_tokens=None,
                    )

                    # # some turns have tool calls, in which case the content
                    # # is actually a list of dicts
                    # content = ""
                    # for i in turn["turn"]:
                    #     c = i.get("content", "")
                    #     if isinstance(c, str):
                    #         if len(content) > 0:
                    #             # because we're concatenating lines together
                    #             content += "\n"
                    #         content += c
                    #     elif isinstance(c, list):
                    #         for entry in c:
                    #             c2 = entry.get("content", "")
                    #             if isinstance(c2, str):
                    #                 if len(content) > 0:
                    #                     content += "\n"
                    #                 content += c2

                    Turn.create(
                        evalsetrun=row.evalsetrun,
                        dataset=dataset,
                        datasetrow=row,
                        turn_number=turn_ix + 1,
                        turn=json.dumps(turn["turn"]),
                        role=turn["role"],
                        content=content,
                        tool_used=turn["tool_used"],
                        system_prompt=turn["system_prompt"],
                        context=json.dumps(
                            [item for d in turns[:turn_ix] for item in d["turn"]]
                        ),  # concatenate all turns except the current
                        is_final_turn_in_input=turn["is_final_turn_in_input"],
                        is_completion=False,
                        prompt_tokens=None,
                    )
    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    # Do completions, if necessary
    try:
        if evalsetrun.do_completion:
            # We do this by creating new turns
            runner.logger.info("Generating completions")

            # Set up a ThreadPoolExecutor to manage threading
            n_workers = runner.configuration.get("max_workers", 1)
            runner.logger.info(f"Generating completions with {n_workers} workers.")
            if n_workers == 1:
                completions = []
                for turn in evalsetrun.turns:
                    completion = turn.get_completion(
                        include_system_prompt=False  # TODO - pull this from config
                    )
                    if completion is not None:
                        completions.append(completion)
            elif n_workers > 1:

                with ThreadPoolExecutor(max_workers=n_workers) as executor:
                    # Submit all turns to the executor
                    futures = [
                        executor.submit(
                            turn.get_completion, include_system_prompt=False
                        )  # TODO - pull this from config
                        for turn in evalsetrun.turns
                    ]

                    # Optionally, wait for all futures to complete and handle exceptions
                    for future in as_completed(futures):
                        try:
                            future.result()  # If you need to catch exceptions or ensure completion
                        except Exception as e:
                            runner.logger.exception(
                                "An error occurred during processing"
                            )
                completions = [
                    future.result() for future in futures if future.result() is not None
                ]

            runner.logger.info(f"Saving completions to database.")
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

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    # Now compute metircs in parallel
    try:
        # Set up a ThreadPoolExecutor to manage threading
        n_workers = runner.configuration.get("max_workers", 1)
        runner.logger.info(f"Generating metrics with {n_workers} workers.")

        # collect turns to run metrics on
        turns_to_evaluate = []
        for turn in evalsetrun.turns:
            # only do completions
            if turn.is_completion and evalsetrun.do_completion:
                turns_to_evaluate.append(turn)
            # or do all turns
            elif not evalsetrun.do_completion:
                turns_to_evaluate.append(turn)

        # collect function calls to make
        # here, we'll use the metric ordering established in evalsetrun.metric_graph
        rubric_count = 0
        for turn in turns_to_evaluate:
            turn.metrics_to_evaluate = []
            # metric dependencies happen WITHIN turns, rather than across
            # this means I can associate a sequence of metrics within each turn
            # but then have the turns execute them in parallel
            # each turn will keep track of its own set of metrics
            for metric_instance in json.loads(evalsetrun.metrics_graph_ordered_list):
                turn.metrics_to_evaluate.append(metric_instance)
                if metric_instance.get("evaluation_type") == "rubric":
                    rubric_count += 1

        runner.logger.info(
            f"Metrics will include up to {rubric_count} rubric evaluations."
        )
        if n_workers == 1:
            metrics = []
            for turn in turns_to_evaluate:
                # it already knows its arguments
                turn_metrics = turn.compute_metrics()
                # metric = compute_metric(**arg)
                for m in turn_metrics:
                    if m.get("evaluation_type", None) is None:
                        runner.logger.exception(
                            f"Metric {m} does not have a value for the key `type`."
                        )
                    if m.get("metric_value", None) is None:
                        runner.logger.exception(
                            f"Metric {m} does not have a value for the key `metric_value`."
                        )
                metrics += turn_metrics
        else:

            # if we want the dependencies to be obeyed, we must

            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = []
                for turn in turns_to_evaluate:
                    futures.append(executor.submit(turn.compute_metrics))

                # Wait for all futures to complete and handle exceptions
                for future in futures:
                    try:
                        future.result()  # If you need to catch exceptions or ensure completion
                    except Exception as e:
                        runner.logger.exception("An error occurred during processing")
                metrics = []
                for future in futures:
                    metrics += future.result()

        runner.logger.info(f"Saving {len(metrics)} metrics to database.")
        for metric in metrics:
            # TODO - speed this up somehow
            TurnMetric.create(
                turn=metric["turn"],
                evalsetrun=metric["turn"].evalsetrun,
                dataset=metric["turn"].dataset,
                datasetrow=metric["turn"].datasetrow,
                evaluation_name=metric["evaluation_name"],
                evaluation_type=metric["evaluation_type"],
                metric_name=metric["metric_name"],
                metric_value=metric["metric_value"],
                kwargs=metric["kwargs"],
                depends_on=json.dumps(metric["depends_on"]),
                source=metric["source"],
                rubric_prompt=metric.get("rubric_prompt", None),
                rubric_completion=metric.get("rubric_completion", None),
                rubric_model=metric.get("rubric_model", None),
                rubric_completion_tokens=metric.get("rubric_completion_tokens", None),
                rubric_prompt_tokens=metric.get("rubric_prompt_tokens", None),
                rubric_score=metric.get("rubric_score", None),
            )

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    runner.logger.info(f"Evaluation run complete.")


if __name__ == "__main__":
    # parse arguments

    ################################################################################
    ## Parse inputs and load config files
    ################################################################################

    # Create the parser
    parser = argparse.ArgumentParser()
    # Add an argument
    parser.add_argument(
        "--eval_name",
        type=str,
        help="Which eval set in evals.yaml you want to run",
    )
    parser.add_argument(
        "--evals_path",
        type=str,
        help="Path to the evaluation file evals.yaml you want to run. Deafult is configuration/evals.yaml.",
    )
    parser.add_argument(
        "--config_path",
        type=str,
        help="Which config file to use",
        default="config.yaml",
    )
    # Parse the argument
    args = parser.parse_args()

    run(**vars(args))
