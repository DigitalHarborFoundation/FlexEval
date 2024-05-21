import argparse
import os
import shutil
import subprocess
from datetime import datetime
import yaml
import sqlite3
import unittest
import sys

from helpers import (
    MyDumper,
    extract_results_paths,
    load_templates,
    sync_directories,
    read_save_data,
)

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

    # from pathlib import Path
    # sys.path.append(str(Path(__file__).parent))

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
    # Parse the argument
    args = parser.parse_args()

    # Load configs
    with open("config-dev.yaml") as file:
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

    def get_eval_class_name(score_type, eval_suite):
        if score_type == "per_turn_by_role":
            eval_class_name = "MetricTurnByRole"
            completion_fn_kwargs = None
        elif score_type == "completion":
            eval_class_name = "MetricCompletionOnly"
            completion_fn_kwargs = eval_suite["completion"]
        elif score_type == "per_conversation_by_role":
            eval_class_name = "MetricConversationByRole"
            completion_fn_kwargs = None
        else:
            raise Exception(
                f'Error: function eval score must be either "all_by_role" or "completion". You listed {score_type}.',
            )
        return eval_class_name, completion_fn_kwargs

    # easier than putting "if not None" below
    if eval_suite_to_run["function_metrics"] is None:
        eval_suite_to_run["function_metrics"] = []
    if eval_suite_to_run["rubric_metrics"] is None:
        eval_suite_to_run["rubric_metrics"] = []

    run_kwargs_dict = {}
    run_kwargs_dict["grader"] = {}
    run_kwargs_dict["completion"] = {}

    for i, j in eval_suite_to_run["grader_llm"].items():
        run_kwargs_dict["grader"][i] = j
    for i, j in eval_suite_to_run["completion"].items():
        run_kwargs_dict["completion"][i] = j
    run_kwargs_list = [
        f"{i}: '{j}'" for i, j in run_kwargs_dict["completion"].items()
    ] + [f"{i}: '{j}'" for i, j in run_kwargs_dict["grader"].items()]
    # print(run_kwargs_list)
    # sys.exit()

    for function_metric in eval_suite_to_run["function_metrics"]:
        # Fill out template definition and write to file
        # Determine which metric class to use
        eval_class_name, completion_fn_kwargs = get_eval_class_name(
            function_metric["score"], eval_suite_to_run
        )

        function_metric_template_filled = function_metric_template.format(
            function_metric_name=function_metric["name"],
            eval_class_name=eval_class_name,
            data_path=os.path.abspath(eval_suite_to_run["data"]["path"]),
            completion_fn_name=eval_suite_to_run["completion"].get(
                "function_name", "no_completion_fn"
            ),
            run_kwargs="\n    ".join(run_kwargs_list),
        )
        all_evals += function_metric_template_filled

    for rubric_metric in eval_suite_to_run["rubric_metrics"]:
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
    # TODO We could do this for the grader LLM too
    completion_fn_templated_filled = completion_fn_template.format(
        completion_fn_name=eval_suite_to_run["completion"].get(
            "function_name", "no_completion_fn"
        )
        + "__completion",
        completion_fn_kwargs="\n    ".join(
            [f"{i}: '{j}'" for i, j in eval_suite_to_run["completion"].items()]
        ),
    )

    grader_completion_fn_templated_filled = completion_fn_template.format(
        completion_fn_name=eval_suite_to_run["grader_llm"].get(
            "function_name", "no_completion_fn"
        )
        + "__grader",
        completion_fn_kwargs="\n    ".join(
            [f"{i}: '{j}'" for i, j in eval_suite_to_run["grader_llm"].items()]
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
    with open(
        os.path.join(
            config["output_path"],
            "registry",
            "eval_sets",
            "levi_evals.yaml",
        ),
        "w",
    ) as file:
        file.write(
            yaml.dump(
                {
                    args.eval_suite: {
                        "evals": [
                            f'{i["name"]}.{get_eval_class_name(i["score"], eval_suite_to_run)[0]}'
                            for i in eval_suite_to_run["function_metrics"]
                        ]
                        + [f'{i["name"]}' for i in eval_suite_to_run["rubric_metrics"]],
                    },
                },
                Dumper=MyDumper,
                default_flow_style=False,
            ),
        )

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
        # command = f'PYTHONPATH=$PYTHONPATH:.; oaievalset {eval_suite_to_run["completion"].get("function_name", "no_completion_fn")},{eval_suite_to_run["grader_llm"].get("model", "gpt-3.5-turbo")} {args.eval_suite} --log_to_file {logfile}'
        command = f'oaievalset {eval_suite_to_run["completion"].get("function_name", "no_completion_fn")}__completion,{eval_suite_to_run["grader_llm"].get("function_name", "no_completion_fn")}__grader {args.eval_suite} --log_to_file "{logfile}"'
        # record_path is overwritten, so can't use it for oaievalset
        # command = f'oaieval {eval_suite_to_run["grader_llm"]} {eval_suite_to_run["function_metrics"][0]} --log_to_file {logfile} --record_path {record_path}'
        print(f"running {command}")
        # Run a subprocess with a modified environment
        custom_env = os.environ.copy()
        # for key, value in config["env"].items():
        #     custom_env[key] = str(value)
        custom_env["PYTHONPATH"] = (
            os.path.abspath("./") + os.pathsep + custom_env.get("PYTHONPATH", "")
        )
        # with subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=1, text=True) as proc:
        ##for line in proc.stdout:
        # print(line, end='')  # Print each line as it is received

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
        # eval_lines = [i for i in log_lines if '/tmp/evallogs/' in i]
    results_paths = set(extract_results_paths(log_lines))
    print(results_paths)
    for result_path in results_paths:
        read_save_data(result_path, config["database_path"], run_kwargs_dict)

    # create views
    with sqlite3.connect(config["database_path"]) as conn:
        cursor = conn.cursor()
        # Check if the view exists
        cursor.execute(
            """
            CREATE VIEW IF NOT EXISTS v_summary
                AS
                    SELECT
                        run_metadata.run_id,
                        base_eval as eval_base_name,
                        run_config__completion_fns__0 as endpoint,
                        json_extract(run_config__eval_spec__args,'$.samples_jsonl') as data,
                        run_config__completion_fns__1 as rubric_grader_llm,
                        run_aggregate_score.metric_name as metric_name,
                        run_aggregate_score.metric_aggregate_value as metric_value,
                        run_aggregate_score.aggregation as aggregation,
                        run_aggregate_score.metric_aggregate_value as metric_value,
                        created_at
                        from run_metadata
                        left join run_aggregate_score on run_metadata.run_id = run_aggregate_score.run_id
                        where metric_aggregate_value is not null
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS run_metadata_run_id_index on run_metadata (run_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS run_aggregate_score_run_id_index on run_aggregate_score (run_id);"
        )
