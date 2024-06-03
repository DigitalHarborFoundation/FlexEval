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

# Features to add:
# - allow comparison with 'ideal' responses
# - collect costs for evaluations (and perhaps estimate them??)
# -


if __name__ == "__main__":
    ################################################################################
    ## Verify configuration
    ################################################################################

    print("Verifying configuration...")
    suite = unittest.defaultTestLoader.discover("./", pattern="verify_installation.py")
    # Run the tests and capture the results
    result = unittest.TextTestRunner().run(suite)
    # Check if there were any failures or errors
    test_failed = not result.wasSuccessful()
    if test_failed:
        print(
            "Something is wrong with your configuration. See error messages for details. Exiting."
        )
        sys.exit()

    ################################################################################
    ## Parse inputs and load config files
    ################################################################################

    # Create the parser
    parser = argparse.ArgumentParser()
    # Add an argument
    parser.add_argument(
        "eval_suite",
        type=str,
        help="Which eval set in evals.yaml you want to run",
    )
    parser.add_argument(
        "config_file", type=str, help="Which config file to use", default="config.yaml"
    )
    # Parse the argument
    args = parser.parse_args()

    # Load configs
    with open(args.config_file) as file:
        config = yaml.safe_load(file)
    (
        function_metric_template,
        rubric_metric_template,
        completion_fn_template,
    ) = load_templates(
        config,
    )

    # Load evals to run
    with open(config["evals_path"]) as file:
        available_evals = yaml.safe_load(file)
    assert (
        args.eval_suite in available_evals
    ), f'Suite {args.eval_suite} is not defined in file {config["evals_path"]}. Available suites are: {", ".join(available_evals.keys())}'
    eval_suite_to_run = available_evals[args.eval_suite]

    # Get the list of available evals
    with open(config["evals_path"]) as file:
        available_evals = yaml.safe_load(file)

    # Clean up the 'registry' directory from previous runs
    for root, dirs, files in os.walk(config["output_path"]):
        for file in files:
            if not file.startswith("."):
                file_path = os.path.join(root, file)
                os.remove(file_path)

    ################################################################################
    ## Verify structure of config files
    ################################################################################

    # helps avoid bugs later on
    for entry in ["grader_llm", "function_metrics", "completion", "rubric_metrics"]:
        if eval_suite_to_run.get(entry, None) is None:
            eval_suite_to_run[entry] = {}

    ################################################################################
    ## Construct OpenAI-complatible YAML files for evals, eval suites, and completion functions
    ################################################################################

    # Construct the evals yaml file
    all_evals = ""

    def get_eval_class_name(metric, eval_suite):

        # make sure we can call the function
        assert (
            metric.get("name") in globals()
        ), f"{metric.get('name')} is not found in the namespace"
        # TODO - why does this fail?
        assert callable(
            globals()[metric.get("name")]
        ), f"{metric.get('name')} is not a callable function"

        fn = globals()[metric.get("name")]
        input_types = helpers.detect_input_type(fn)
        # If it's a turn-based function and we are doing NO completions
        if "turn" in input_types.keys() and metric.get("completion", False) is False:
            eval_class_name = "TurnMetric"
            completion_fn_kwargs = None
        # if it's a turn-based function and we ARE doing completions
        elif "turn" in input_types.keys() and metric.get("completion", False) is True:
            eval_class_name = "CompletionMetric"
            completion_fn_kwargs = eval_suite["completion_llm"]
        # if it's a conversation-based metric, we are (by default) not doing completions
        elif (
            "conversation" in input_types.keys()
            and metric.get("completion", False) is False
        ):
            eval_class_name = "ConversationMetric"
            completion_fn_kwargs = None
        elif (
            "conversation" in input_types.keys()
            and metric.get("completion", False) is True
        ):
            raise Exception(
                f"""Error: You chose the function {metric.get("name")} and 'completion: true', but that function operates on entire conversations, not individual turns (including completion turns). Try setting 'completion: false'.""",
            )
        return eval_class_name, completion_fn_kwargs

    # easier than putting "if not None" below
    if eval_suite_to_run["function_metrics"] is None:
        eval_suite_to_run["function_metrics"] = []
    if eval_suite_to_run["rubric_metrics"] is None:
        eval_suite_to_run["rubric_metrics"] = []

    run_kwargs_dict = {}
    run_kwargs_dict["grader_llm"] = {}
    run_kwargs_dict["completion_llm"] = {}

    for i, j in eval_suite_to_run.get("grader_llm", {}).items():
        run_kwargs_dict["grader_llm"][i] = j
    for i, j in eval_suite_to_run.get("completion_llm", {}).items():
        run_kwargs_dict["completion_llm"][i] = j
    run_kwargs_list = [
        f"{i}: '{j}'" for i, j in run_kwargs_dict["completion_llm"].items()
    ] + [f"{i}: '{j}'" for i, j in run_kwargs_dict["grader_llm"].items()]

    for function_metric in eval_suite_to_run["function_metrics"]:
        # Fill out template definition and write to file
        # Determine which metric class to use
        eval_class_name, completion_fn_kwargs = get_eval_class_name(
            function_metric, eval_suite_to_run
        )

        function_metric_template_filled = function_metric_template.format(
            function_metric_name=function_metric["name"],
            eval_class_name=eval_class_name,
            data_path=os.path.abspath(eval_suite_to_run["data"]["path"]),
            completion_fn_name=eval_suite_to_run.get(
                "completion_llm", {"function_name": "no_completion_fn"}
            ).get("function_name", "no_completion_fn"),
            run_kwargs="\n    ".join(run_kwargs_list),
        )
        all_evals += function_metric_template_filled

    for rubric_metric in eval_suite_to_run.get("rubric_metrics", []):
        # Fill out template definition and write to file
        # Determine which metric class to use
        # eval_class_name, completion_fn, completion_api_key = get_eval_class_name(rubric["score"], eval_suite_to_run)
        function_metric_template_filled = rubric_metric_template.format(
            data_path=os.path.abspath(eval_suite_to_run["data"]["path"]),
            rubric_metric=rubric_metric["name"],
        )
        all_evals += function_metric_template_filled + "\n"

    # Save the eval registry yaml file
    with open(
        os.path.join(config["output_path"], "registry", "evals", "levi_evals.yaml"),
        "w",
    ) as outfile:
        outfile.write(all_evals)

    # Fill out the completion_fn registry entry. The name will match the completion_fn string
    # specified in the evals.yaml file
    completion_fn_templated_filled = completion_fn_template.format(
        completion_fn_name=eval_suite_to_run.get(
            "completion_llm", {"function_name": "no_completion_fn"}
        ).get("function_name", "no_completion_fn")
        + "__completion",
        completion_fn_kwargs="\n    ".join(
            [
                f"{i}: '{j}'"
                for i, j in eval_suite_to_run.get("completion_llm", {}).items()
            ]
        ),
    )

    grader_completion_fn_templated_filled = completion_fn_template.format(
        completion_fn_name=eval_suite_to_run.get(
            "grader_llm", {"function_name": "no_completion_fn"}
        ).get("function_name", "no_completion_fn")
        + "__grader",
        completion_fn_kwargs="\n    ".join(
            [f"{i}: '{j}'" for i, j in eval_suite_to_run.get("grader_llm", {}).items()]
        ),
    )
    completion_fn_templated_filled = (
        completion_fn_templated_filled + "\n\n" + grader_completion_fn_templated_filled
    )

    # Save the completion function
    with open(
        os.path.join(
            config["output_path"],
            "registry",
            "completion_fns",
            "levi_completion_functions.yaml",
        ),
        "w",
    ) as outfile:
        outfile.write(completion_fn_templated_filled)

    # Create an eval suite with the specified evals in it
    function_evaluation_yaml = yaml.dump(
        {
            args.eval_suite: {
                "evals": [
                    f'{i["name"]}.{get_eval_class_name(i, eval_suite_to_run)[0]}'
                    for i in eval_suite_to_run["function_metrics"]
                ]
                + [f'{i["name"]}' for i in eval_suite_to_run["rubric_metrics"]],
            },
        },
        Dumper=MyDumper,
        default_flow_style=False,
    )
    print("Running function evaluations:\n")
    print(function_evaluation_yaml)
    with open(
        os.path.join(
            config["output_path"],
            "registry",
            "eval_sets",
            "levi_evals.yaml",
        ),
        "w",
    ) as file:
        file.write(function_evaluation_yaml)

    # Copy the rubrics
    shutil.copy2(
        config["rubric_metrics_path"],
        os.path.join(config["output_path"], "registry", "modelgraded/"),
    )

    ################################################################################
    ## Make written files available to OpenAI Evals
    ## Python files are made available by making the llm-evals/ map to the directory from which oaievalset is run
    ## Which then looks at the registry yaml file for which class to import
    ## Registry entries are made available by putting them in ~/.evals, which oaievals looks in when starting
    ################################################################################

    # Sync yaml files to local registry, so as to not pollute the evals library
    destination = os.path.expanduser("~/.evals/")
    source = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "evals_sync/registry/"
    )
    synced_files = sync_directories(source, destination)

    ################################################################################
    ## Run evals and collect stdout and stderr
    ################################################################################

    try:
        # Run the command and capture output
        logfile = os.path.join(
            config["logs_path"],
            f"log-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt",
        )
        # Syntax is "oaievalset $completion_fn_1,$completion_fn_2 $suite_name"
        # The comma-separated list is a list of (usually) LLMs.
        # The first is used to complete conversations, and the last is used in machine-graded evals
        # to evaluate completions.
        # If there is only one listed, it's used for both.
        command = f'oaievalset {eval_suite_to_run.get("completion_llm", {}).get("function_name", "no_completion_fn")}__completion,{eval_suite_to_run["grader_llm"].get("function_name", "no_completion_fn")}__grader {args.eval_suite} --log_to_file "{logfile}"'
        # record_path is overwritten, so can't use it for oaievalset
        print(f"running {command}")
        # Run a subprocess with a modified environment
        custom_env = os.environ.copy()
        custom_env["PYTHONPATH"] = (
            os.path.abspath("./") + os.pathsep + custom_env.get("PYTHONPATH", "")
        )

        result = subprocess.run(
            command,
            # check=True,
            capture_output=True,  # puts results in result.stdout, result.stderr
            text=True,  # pretty-print output
            shell=True,  # runs in current shell/venv
            env=custom_env,
            bufsize=1,
        )
        print(f"Std output: {result.stdout}")
        print(f"Std error: {result.stderr}")

    except subprocess.CalledProcessError as e:
        # This will catch errors from subprocess.run when check=True
        print(f"Command failed with return code {e.returncode}")
        print(f"Std output: {e.stdout}")
        print(f"Error output: {e.stderr}")

        # 'e' contains the result of the subprocess
        if e.stderr:
            print(e.stderr)

    ################################################################################
    ## Save the results to a SQLite database
    ################################################################################

    # # Look through logfile and find where results were written to
    with open(logfile, "r") as file:
        log_lines = file.readlines()
    results_paths = set(extract_results_paths(log_lines))
    for result_path in results_paths:
        read_save_data(result_path, config["database_path"], run_kwargs_dict)

    # create views
    with sqlite3.connect(config["database_path"]) as conn:
        cursor = conn.cursor()

        cursor.execute("DROP VIEW IF EXISTS v_metrics")
        cursor.execute(
            """
            CREATE VIEW IF NOT EXISTS v_metrics AS
            SELECT
            -- sample_id is row number in dataset
            run_single_score.run_id,
            sample_id,
            SUBSTR(sample_id, LENGTH(sample_id) - INSTR(REVERSE(sample_id), '.') + 2) as row_number,
            -- dataset
            json_extract(run_config__eval_spec__args, '$.samples_jsonl') AS data_file,
            json_extract(data, '$.turn') AS turn,
            split,
            --todo - update this 
            CASE 
                WHEN split = 'CompletionMetric' THEN 'assistant'
                WHEN split = 'ConversationMetric' THEN 'conversation'
                ELSE json_extract(data, '$.role')
            END AS role,
            COALESCE(
                json_extract(data, '$.score'),
                json_extract(data, '$.metric_value')
            ) AS metric_value,
            json_extract(run_metadata.run_config__eval_spec__args, '$.run_kwargs.completion_llm.model_name') model_name,
            base_eval,
            json_extract(data, '$.function_metric_name') AS function_metric_name,
            json_extract(data, '$.content') AS content
        FROM run_single_score
        INNER JOIN run_metadata ON run_single_score.run_id = run_metadata.run_id
        WHERE type = 'metrics'
        """
        )

        cursor.execute(
            """
        CREATE VIEW IF NOT EXISTS v_most_recent_eval AS
           WITH ranked_runs AS (
            SELECT
                    run_id,
                    created_at,
                    base_eval,
                    ROW_NUMBER() OVER (PARTITION BY base_eval ORDER BY created_at DESC) AS rn
                FROM
                    run_metadata
            )
            SELECT
                run_id,
                created_at,
                base_eval
            FROM
                ranked_runs
            WHERE
                rn = 1;
            """
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS run_metadata_run_id_index on run_metadata (run_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS run_metadata_created_at_index on run_metadata (created_at);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS run_single_score_run_id_index on run_single_score (run_id);"
        )
