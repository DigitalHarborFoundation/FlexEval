import argparse
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
import random as rd

import json
from classes.EvalRunner import EvalRunner
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.Turn import Turn
from classes.Metric import Metric
import dotenv
import compute_metrics

# Levels of abstraction -
# Dataset
# Thread
# Turn
# Message
# ToolCall
# Metric

# Features to add:
# - allow comparison with 'ideal' responses


def run(eval_name: str, evals_path: str, config_path: str, clear_tables=False):
    """Runs the evaluations.
    We want this to be callable by both the CLI and the webapp
    That means it needs to do argument parsing BEFORE this is called

    TODO - for webapp, config should be an argument here ^

    param: clear_tables - if True, deletes any existing data in the output database. Otherwise, appends
    """
    # TODO - make evals.yaml file path configurable
    runner = EvalRunner(
        eval_name=eval_name,
        config_path=config_path,
        evals_path=evals_path,
        clear_tables=clear_tables,
    )
    dotenv.load_dotenv(runner.configuration["env_file"])
    
    rubrics = {}
    for rf in runner.configuration["rubric_metrics_path"]:
        print('DEBUG - FOUND RUBRIC FILE', rf)
        with open(rf) as file:
            new_rubrics = yaml.safe_load(file)
            for key, value in new_rubrics.items():
                if key not in rubrics:
                    rubrics[key] = value
    
    print('DEBUG - LOADED RUBRICS', rubrics)
    
    
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
            # only save rubrics that will actually be used
            rubrics=json.dumps(
                {
                    i["evaluation_name"]: rubrics[i["evaluation_name"]]
                    for i in runner.metrics_graph_ordered_list
                    if i["evaluation_type"] == "rubric"
                }
            ),
            clear_tables=clear_tables,
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
        
        max_n_conversation_threads = runner.configuration.get("max_n_conversation_threads", None)
        nb_evaluations_per_thread = runner.configuration.get("nb_evaluations_per_thread", None)
        runner.logger.info(f"Running eval with max number of conversation threads: {max_n_conversation_threads} and {nb_evaluations_per_thread} evaluation(s) per thread")
        
        # set random seed
        rd_seed = runner.configuration.get("random_seed_conversation_sampling", 1)
        rd.seed(rd_seed)
        runner.logger.info(f"Set random seed to {rd_seed}")
        
        for filename in evalsetrun.get_datasets():
            # these will automatically be saved as a property of evalsetrun
            Dataset.create(evalsetrun=evalsetrun,
                           filename=filename,
                           max_n_conversation_threads=max_n_conversation_threads,
                           nb_evaluations_per_thread=nb_evaluations_per_thread)
            runner.logger.info(f"Created dataset from {filename}. Max number of conversation threads: {max_n_conversation_threads}, Nb evaluations per thread: {nb_evaluations_per_thread}")

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    try:
        runner.logger.info("Parsing data files")
        for dataset in evalsetrun.datasets:
            runner.logger.debug(f"Loading data from {dataset.filename}")
            dataset.load_data()
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

    #######################################################
    #################  Compute Metrics  ###################
    #######################################################

    try:
        # Set up a ThreadPoolExecutor to manage threading
        n_workers = runner.configuration.get("max_workers", 1)
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

        for level, object_list in object_lists_by_level.items():
            # Add the metrics to objects at this level
            compute_metrics.add_all_metrics_to_objects(
                object_list, metrics_by_level.get(level, [])
            )
            # Update the count of how many rubrics might be run based on rubric evals at this level
            rubric_count += compute_metrics.count_rubric_metrics(object_list)

        runner.logger.info(
            f"Metrics will include up to {rubric_count} rubric evaluations."
        )
        if n_workers == 1:
            metrics = []
            # del object_lists_by_level["Thread"]
            # del object_lists_by_level["Turn"]
            # del object_lists_by_level["Message"]
            # del object_lists_by_level["ToolCall"]
            for level, object_list in object_lists_by_level.items():
                runner.logger.info(f"Computing metrics for level: {level}")
                for object in object_list:
                    cur_metrics = compute_metrics.compute_metrics(object)
                    for m in cur_metrics:
                        if m.get("evaluation_type", None) is None:
                            runner.logger.exception(
                                f"Metric {m} does not have a value for the key `type`."
                            )
                        if m.get("metric_value", None) is None:
                            runner.logger.exception(
                                f"Metric {m} does not have a value for the key `metric_value`."
                            )

                    metrics += cur_metrics

        else:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = []
                for level, object_list in object_lists_by_level.items():
                    for object in object_list:
                        futures.append(
                            executor.submit(compute_metrics.compute_metrics, object)
                        )

                # Wait for all futures to complete and handle exceptions
                for fid, future in enumerate(futures):
                    try:
                        future.result()  # If you need to catch exceptions or ensure completion
                        if fid%100 == 0:
                            runner.logger.info(f'Metrics futures resulted: {fid} / {len(futures)}')
                    except Exception as e:
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

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    runner.logger.info(f"Evaluation run complete.")

    # remove logging handler so we don't get repeat logs if we call run() twice
    handlers = runner.logger.handlers[:]
    for handler in handlers:
        runner.logger.removeHandler(handler)


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
        "--clear_tables",
        action="store_true",
        help="Set this flag to drop existing tables in the results database before running. Useful during development.",
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
