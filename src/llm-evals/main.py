import argparse
import os
import shutil
import subprocess
from datetime import datetime
import yaml
import sqlite3
import unittest
import sys
import helpers
from concurrent.futures import ThreadPoolExecutor


import dotenv

dotenv.load_dotenv(".env")

from configuration.function_metrics import *

from helpers import (
    MyDumper,
    extract_results_paths,
    load_templates,
    sync_directories,
    read_save_data,
)
from classes.EvalRunner import EvalRunner
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.DatasetRow import DatasetRow
from classes.Turn import Turn
from classes.TurnMetric import TurnMetric, compute_metric

# Features to add:
# - allow comparison with 'ideal' responses
# - collect costs for evaluations (and perhaps estimate them??)
# -


def run(args):
    """Runs the evaluations.
    We want this to be callable by both the CLI and the webapp
    That means it needs to do argument parsing BEFORE this is called

    TODO - for webapp, config should be an argument here ^
    """

    runner = EvalRunner(eval_name=args.eval_name, config_filename=args.config_filename)
    try:
        runner.logger.info("Creating EvalSetRun")
        evalsetrun = EvalSetRun.create(
            name=runner.eval.get("name", ""),
            notes=runner.eval.get("notes", ""),
            metrics=json.dumps(runner.eval.get("metrics", "")),
            dataset_files=json.dumps(runner.eval.get("data", "")),
            do_completion=runner.eval.get("do_completion", False),
            completion_llm=json.dumps(runner.eval.get("completion_llm", None)),
            model_name=json.dumps(
                runner.eval.get("completion_llm", {}).get("model_name", None)
            ),
            grader_llm=json.dumps(runner.eval.get("grader_llm", None)),
        )
    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    try:
        runner.logger.info("Loading data")
        for filename in evalsetrun.get_datasets():
            runner.logger.debug(f"Loading data file {filename}")
            with open(filename, "r") as infile:
                contents = infile.read()
            # these will automatically be saved as a property of evalsetrun
            Dataset.create(
                evalsetrun=evalsetrun,
                filename=filename,
                contents=contents,
            )
    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    try:
        runner.logger.info("Parsing data files")
        for dataset in evalsetrun.datasets:
            runner.logger.debug(f"Parsing data file {dataset.filename}")

            rows = dataset.get_rows()
            runner.validate_dataset(dataset.filename, rows)
            for row in rows:
                DatasetRow.create(
                    dataset=dataset,
                    evalsetrun=dataset.evalsetrun,
                    input=json.dumps(row.get("input", None)),
                    ideals=json.dumps(row.get("ideals", None)),
                    metadata=json.dumps(
                        {k: v for k, v in row.items() if k not in ["input", "ideals"]}
                    ),
                )
    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    try:
        runner.logger.info("Parsing turns")
        for dataset in evalsetrun.datasets:
            for row in dataset.rows:
                turns = row.get_turns()
                for turn_ix, turn in enumerate(turns):
                    assert isinstance(turn["turn"], list)
                    Turn.create(
                        evalsetrun=row.evalsetrun,
                        dataset=dataset,
                        datasetrow=row,
                        turn_number=turn_ix + 1,
                        turn=json.dumps(turn["turn"]),
                        role=turn["role"],
                        content="\n".join([i.get("content", "") for i in turn["turn"]]),
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
                    for future in futures:
                        try:
                            future.result()  # If you need to catch exceptions or ensure completion
                        except Exception as e:
                            runner.logger.exception(
                                "An error occurred during processing"
                            )
                completions = [
                    future.result() for future in futures if future.result() is not None
                ]

            for completion in completions:
                # {"choices": [{"message": {"content": "hi", "role": "assistant"}}]}
                for message in completion:
                    assert isinstance(message["turn"], list)
                    print(message["turn"])
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
                        context=message["context"],
                        is_final_turn_in_input=message["is_final_turn_in_input"],
                        is_completion=True,
                        prompt_tokens=message["prompt_tokens"],
                        completion_tokens=message["completion_tokens"],
                    )

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    # Now compute metircs in parallel
    try:
        # We do this by creating new turns
        runner.logger.info("Generating function metrics")

        # Set up a ThreadPoolExecutor to manage threading
        n_workers = runner.configuration.get("max_workers", 1)
        runner.logger.info(f"Generating function metrics with {n_workers} workers.")
        if n_workers == 1:
            metrics = []
            # just calculate metrics on completions
            if evalsetrun.do_completion:
                # for each metric

                for target_metric in json.loads(evalsetrun.metrics).get("function", []):
                    metric_name = target_metric.get("name", None)

                    for turn in evalsetrun.turns:
                        if turn.is_completion:
                            metric = compute_metric(
                                metric_name=metric_name,
                                metric_definition=target_metric,
                                turn=turn,
                            )
                            metrics += metric
        elif n_workers > 1:

            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                # Submit all turns to the executor

                for target_metric in json.loads(evalsetrun.metrics).get("function", []):
                    metric_name = target_metric.get("name", None)

                    for turn in evalsetrun.turns:
                        futures.append(
                            executor.submit(
                                compute_metric,
                                metric_name=metric_name,
                                metric_definition=target_metric,
                                turn=turn,
                            )  # TODO - pull this from config
                        )

                # Optionally, wait for all futures to complete and handle exceptions
                for future in futures:
                    try:
                        future.result()  # If you need to catch exceptions or ensure completion
                    except Exception as e:
                        runner.logger.exception("An error occurred during processing")
                metrics = []
                for future in futures:
                    metrics += future.result()

        for metric in metrics:
            # assert isinstance(metric["turn"], list)
            print(metric)
            TurnMetric.create(
                turn=metric["turn"],
                evalsetrun=metric["turn"].evalsetrun,
                dataset=metric["turn"].dataset,
                datasetrow=metric["turn"].datasetrow,
                metric_definition=json.dumps(metric["metric_definition"]),
                metric_function_name=metric["metric_function_name"],
                metric_name=metric["metric_name"],
                metric_value=metric["metric_value"],
                metric_kwargs=metric["metric_kwargs"],
                metric_source=metric["metric_source"],
            )

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    # ################################################################################
    # ## Verify configuration
    # ################################################################################

    # (
    #     function_metric_template,
    #     rubric_metric_template,
    #     completion_fn_template,
    # ) = load_templates(
    #     config,
    # )

    # # Load evals to run
    # with open(config["evals_path"]) as file:
    #     available_evals = yaml.safe_load(file)
    # assert (
    #     args.eval_suite in available_evals
    # ), f'Suite {args.eval_suite} is not defined in file {config["evals_path"]}. Available suites are: {", ".join(available_evals.keys())}'
    # eval_suite_to_run = available_evals[args.eval_suite]

    # # Get the list of available evals
    # with open(config["evals_path"]) as file:
    #     available_evals = yaml.safe_load(file)

    # # Clean up the 'registry' directory from previous runs
    # for root, dirs, files in os.walk(config["output_path"]):
    #     for file in files:
    #         if not file.startswith("."):
    #             file_path = os.path.join(root, file)
    #             os.remove(file_path)

    # ################################################################################
    # ## Verify structure of config files
    # ################################################################################

    # # helps avoid bugs later on
    # for entry in ["grader_llm", "function_metrics", "completion", "rubric_metrics"]:
    #     if eval_suite_to_run.get(entry, None) is None:
    #         eval_suite_to_run[entry] = {}

    # ################################################################################
    # ## Construct OpenAI-complatible YAML files for evals, eval suites, and completion functions
    # ################################################################################

    # ################################################################################
    # ## Construct OpenAI-complatible YAML files for evals, eval suites, and completion functions
    # ################################################################################

    # # Construct the evals yaml file
    # all_evals = ""

    # def get_eval_class_name(metric, eval_suite):

    #     # make sure we can call the function
    #     assert (
    #         metric.get("name") in globals()
    #     ), f"{metric.get('name')} is not found in the namespace"
    #     # TODO - why does this fail?
    #     assert callable(
    #         globals()[metric.get("name")]
    #     ), f"{metric.get('name')} is not a callable function"

    #     fn = globals()[metric.get("name")]
    #     input_types = helpers.detect_input_type(fn)
    #     # If it's a turn-based function and we are doing NO completions
    #     if "turn" in input_types.keys() and metric.get("completion", False) is False:
    #         eval_class_name = "TurnMetric"
    #         completion_fn_kwargs = None
    #     # if it's a turn-based function and we ARE doing completions
    #     elif "turn" in input_types.keys() and metric.get("completion", False) is True:
    #         eval_class_name = "CompletionMetric"
    #         completion_fn_kwargs = eval_suite["completion_llm"]
    #     # if it's a conversation-based metric, we are (by default) not doing completions
    #     elif (
    #         "conversation" in input_types.keys()
    #         and metric.get("completion", False) is False
    #     ):
    #         eval_class_name = "ConversationMetric"
    #         completion_fn_kwargs = None
    #     elif (
    #         "conversation" in input_types.keys()
    #         and metric.get("completion", False) is True
    #     ):
    #         raise Exception(
    #             f"""Error: You chose the function {metric.get("name")} and 'completion: true', but that function operates on entire conversations, not individual turns (including completion turns). Try setting 'completion: false'.""",
    #         )
    #     return eval_class_name, completion_fn_kwargs

    # # easier than putting "if not None" below
    # if eval_suite_to_run["function_metrics"] is None:
    #     eval_suite_to_run["function_metrics"] = []
    # if eval_suite_to_run["rubric_metrics"] is None:
    #     eval_suite_to_run["rubric_metrics"] = []

    # run_kwargs_dict = {}
    # run_kwargs_dict["grader_llm"] = {}
    # run_kwargs_dict["completion_llm"] = {}

    # for i, j in eval_suite_to_run.get("grader_llm", {}).items():
    #     run_kwargs_dict["grader_llm"][i] = j
    # for i, j in eval_suite_to_run.get("completion_llm", {}).items():
    #     run_kwargs_dict["completion_llm"][i] = j
    # run_kwargs_list = [
    #     f"{i}: '{j}'" for i, j in run_kwargs_dict["completion_llm"].items()
    # ] + [f"{i}: '{j}'" for i, j in run_kwargs_dict["grader_llm"].items()]

    # for function_metric in eval_suite_to_run["function_metrics"]:
    #     # Fill out template definition and write to file
    #     # Determine which metric class to use
    #     eval_class_name, completion_fn_kwargs = get_eval_class_name(
    #         function_metric, eval_suite_to_run
    #     )

    #     function_metric_template_filled = function_metric_template.format(
    #         function_metric_name=function_metric["name"],
    #         eval_class_name=eval_class_name,
    #         data_path=os.path.abspath(eval_suite_to_run["data"]["path"]),
    #         completion_fn_name=eval_suite_to_run.get(
    #             "completion_llm", {"function_name": "no_completion_fn"}
    #         ).get("function_name", "no_completion_fn"),
    #         run_kwargs="\n    ".join(run_kwargs_list),
    #     )
    #     all_evals += function_metric_template_filled

    # for rubric_metric in eval_suite_to_run.get("rubric_metrics", []):
    #     # Fill out template definition and write to file
    #     # Determine which metric class to use
    #     # eval_class_name, completion_fn, completion_api_key = get_eval_class_name(rubric["score"], eval_suite_to_run)
    #     function_metric_template_filled = rubric_metric_template.format(
    #         data_path=os.path.abspath(eval_suite_to_run["data"]["path"]),
    #         rubric_metric=rubric_metric["name"],
    #     )
    #     all_evals += function_metric_template_filled + "\n"

    # # Save the eval registry yaml file
    # with open(
    #     os.path.join(config["output_path"], "registry", "evals", "levi_evals.yaml"),
    #     "w",
    # ) as outfile:
    #     outfile.write(all_evals)

    # # Fill out the completion_fn registry entry. The name will match the completion_fn string
    # # specified in the evals.yaml file
    # completion_fn_templated_filled = completion_fn_template.format(
    #     completion_fn_name=eval_suite_to_run.get(
    #         "completion_llm", {"function_name": "no_completion_fn"}
    #     ).get("function_name", "no_completion_fn")
    #     + "__completion",
    #     completion_fn_kwargs="\n    ".join(
    #         [
    #             f"{i}: '{j}'"
    #             for i, j in eval_suite_to_run.get("completion_llm", {}).items()
    #         ]
    #     ),
    # )

    # grader_completion_fn_templated_filled = completion_fn_template.format(
    #     completion_fn_name=eval_suite_to_run.get(
    #         "grader_llm", {"function_name": "no_completion_fn"}
    #     ).get("function_name", "no_completion_fn")
    #     + "__grader",
    #     completion_fn_kwargs="\n    ".join(
    #         [f"{i}: '{j}'" for i, j in eval_suite_to_run.get("grader_llm", {}).items()]
    #     ),
    # )
    # completion_fn_templated_filled = (
    #     completion_fn_templated_filled + "\n\n" + grader_completion_fn_templated_filled
    # )

    # # Save the completion function
    # with open(
    #     os.path.join(
    #         config["output_path"],
    #         "registry",
    #         "completion_fns",
    #         "levi_completion_functions.yaml",
    #     ),
    #     "w",
    # ) as outfile:
    #     outfile.write(completion_fn_templated_filled)

    # # Create an eval suite with the specified evals in it
    # function_evaluation_yaml = yaml.dump(
    #     {
    #         args.eval_suite: {
    #             "evals": [
    #                 f'{i["name"]}.{get_eval_class_name(i, eval_suite_to_run)[0]}'
    #                 for i in eval_suite_to_run["function_metrics"]
    #             ]
    #             + [f'{i["name"]}' for i in eval_suite_to_run["rubric_metrics"]],
    #         },
    #     },
    #     Dumper=MyDumper,
    #     default_flow_style=False,
    # )
    # print("Running function evaluations:\n")
    # print(function_evaluation_yaml)
    # with open(
    #     os.path.join(
    #         config["output_path"],
    #         "registry",
    #         "eval_sets",
    #         "levi_evals.yaml",
    #     ),
    #     "w",
    # ) as file:
    #     file.write(function_evaluation_yaml)

    # # Copy the rubrics
    # shutil.copy2(
    #     config["rubric_metrics_path"],
    #     os.path.join(config["output_path"], "registry", "modelgraded/"),
    # )

    # ################################################################################
    # ## Make written files available to OpenAI Evals
    # ## Python files are made available by making the llm-evals/ map to the directory from which oaievalset is run
    # ## Which then looks at the registry yaml file for which class to import
    # ## Registry entries are made available by putting them in ~/.evals, which oaievals looks in when starting
    # ################################################################################

    # # Sync yaml files to local registry, so as to not pollute the evals library
    # destination = os.path.expanduser("~/.evals/")
    # source = os.path.join(
    #     os.path.dirname(os.path.abspath(__file__)), "evals_sync/registry/"
    # )
    # synced_files = sync_directories(source, destination)

    # ################################################################################
    # ## Run evals and collect stdout and stderr
    # ################################################################################

    # try:
    #     # Run the command and capture output
    #     logfile = os.path.join(
    #         config["logs_path"],
    #         f"log-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt",
    #     )
    #     # Syntax is "oaievalset $completion_fn_1,$completion_fn_2 $suite_name"
    #     # The comma-separated list is a list of (usually) LLMs.
    #     # The first is used to complete conversations, and the last is used in machine-graded evals
    #     # to evaluate completions.
    #     # If there is only one listed, it's used for both.
    #     command = f'oaievalset {eval_suite_to_run.get("completion_llm", {}).get("function_name", "no_completion_fn")}__completion,{eval_suite_to_run["grader_llm"].get("function_name", "no_completion_fn")}__grader {args.eval_suite} --log_to_file "{logfile}"'
    #     # record_path is overwritten, so can't use it for oaievalset
    #     print(f"running {command}")
    #     # Run a subprocess with a modified environment
    #     custom_env = os.environ.copy()
    #     custom_env["PYTHONPATH"] = (
    #         os.path.abspath("./") + os.pathsep + custom_env.get("PYTHONPATH", "")
    #     )

    #     result = subprocess.run(
    #         command,
    #         # check=True,
    #         capture_output=True,  # puts results in result.stdout, result.stderr
    #         text=True,  # pretty-print output
    #         shell=True,  # runs in current shell/venv
    #         env=custom_env,
    #         bufsize=1,
    #     )
    #     print(f"Std output: {result.stdout}")
    #     print(f"Std error: {result.stderr}")

    # except subprocess.CalledProcessError as e:
    #     # This will catch errors from subprocess.run when check=True
    #     print(f"Command failed with return code {e.returncode}")
    #     print(f"Std output: {e.stdout}")
    #     print(f"Error output: {e.stderr}")

    #     # 'e' contains the result of the subprocess
    #     if e.stderr:
    #         print(e.stderr)

    # ################################################################################
    # ## Save the results to a SQLite database
    # ################################################################################

    # # # Look through logfile and find where results were written to
    # with open(logfile, "r") as file:
    #     log_lines = file.readlines()
    # results_paths = set(extract_results_paths(log_lines))
    # for result_path in results_paths:
    #     read_save_data(result_path, config["database_path"], run_kwargs_dict)

    # # create views
    # with sqlite3.connect(config["database_path"]) as conn:
    #     cursor = conn.cursor()

    #     cursor.execute("DROP VIEW IF EXISTS v_metrics")
    #     cursor.execute(
    #         """
    #         CREATE VIEW IF NOT EXISTS v_metrics AS
    #         SELECT
    #         -- sample_id is row number in dataset
    #         run_single_score.run_id,
    #         sample_id,
    #         SUBSTR(sample_id, LENGTH(sample_id) - INSTR(REVERSE(sample_id), '.') + 2) as row_number,
    #         -- dataset
    #         json_extract(run_config__eval_spec__args, '$.samples_jsonl') AS data_file,
    #         json_extract(data, '$.turn') AS turn,
    #         split,
    #         --todo - update this
    #         CASE
    #             WHEN split = 'CompletionMetric' THEN 'assistant'
    #             WHEN split = 'ConversationMetric' THEN 'conversation'
    #             ELSE json_extract(data, '$.role')
    #         END AS role,
    #         COALESCE(
    #             json_extract(data, '$.score'),
    #             json_extract(data, '$.metric_value')
    #         ) AS metric_value,
    #         json_extract(run_metadata.run_config__eval_spec__args, '$.run_kwargs.completion_llm.model_name') model_name,
    #         base_eval,
    #         json_extract(data, '$.function_metric_name') AS function_metric_name,
    #         json_extract(data, '$.content') AS content
    #     FROM run_single_score
    #     INNER JOIN run_metadata ON run_single_score.run_id = run_metadata.run_id
    #     WHERE type = 'metrics'
    #     """
    #     )

    #     cursor.execute(
    #         """
    #     CREATE VIEW IF NOT EXISTS v_most_recent_eval AS
    #        WITH ranked_runs AS (
    #         SELECT
    #                 run_id,
    #                 created_at,
    #                 base_eval,
    #                 ROW_NUMBER() OVER (PARTITION BY base_eval ORDER BY created_at DESC) AS rn
    #             FROM
    #                 run_metadata
    #         )
    #         SELECT
    #             run_id,
    #             created_at,
    #             base_eval
    #         FROM
    #             ranked_runs
    #         WHERE
    #             rn = 1;
    #         """
    #     )

    #     cursor.execute(
    #         "CREATE INDEX IF NOT EXISTS run_metadata_run_id_index on run_metadata (run_id);"
    #     )
    #     cursor.execute(
    #         "CREATE INDEX IF NOT EXISTS run_metadata_created_at_index on run_metadata (created_at);"
    #     )
    #     cursor.execute(
    #         "CREATE INDEX IF NOT EXISTS run_single_score_run_id_index on run_single_score (run_id);"
    #     )


if __name__ == "__main__":
    # parse arguments

    ################################################################################
    ## Parse inputs and load config files
    ################################################################################

    # Create the parser
    parser = argparse.ArgumentParser()
    # Add an argument
    parser.add_argument(
        "eval_name",
        type=str,
        help="Which eval set in evals.yaml you want to run",
    )
    parser.add_argument(
        "--config_filename",
        type=str,
        help="Which config file to use",
        default="config.yaml",
    )
    # Parse the argument
    args = parser.parse_args()

    run(args)
