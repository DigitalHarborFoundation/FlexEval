import os
import re
import shutil
import json
from flatten_json import flatten
import pandas as pd
import sqlite3
import yaml
import traceback
from datetime import datetime
from typing import Callable, Dict, Any, Type, Tuple, List, get_type_hints


def detect_input_type(func: Callable) -> Dict[str, Type[Any]]:
    """
    Detect and return the input types of a function based on its type annotations.

    Args:
        func (Callable): The function whose input types are to be detected.

    Returns:
        Dict[str, Type[Any]]: A dictionary where the keys are parameter names and the values are their annotated types.
    """
    annotations = get_type_hints(func)
    input_types = {k: v for k, v in annotations.items() if k != "return"}
    return input_types


def load_templates(config: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Load template files based on the provided configuration paths.

    Args:
        config (Dict[str, Any]): A dictionary containing the paths to the template files.

    Returns:
        Tuple[str, str, str]: A tuple containing the content of the function metric template,
                              the rubric metric template, and the completion function template.
    """
    with open(config["rubric_metric_template_path"], "r") as file:
        rubric_metric_template = file.read()

    with open(config["function_metric_template_path"], "r") as file:
        function_metric_template = file.read()

    with open(config["completion_fn_template_path"], "r") as file:
        completion_fn_template = file.read()

    return function_metric_template, rubric_metric_template, completion_fn_template


def sync_directories(source: str, destination: str) -> List[str]:
    """
    Synchronize the contents of the source directory with the destination directory.

    Args:
        source (str): The path of the source directory.
        destination (str): The path of the destination directory.

    Returns:
        List[str]: A list of files that were created or updated in the destination directory.
    """
    created_files = []
    for dirpath, dirnames, filenames in os.walk(source):
        # Construct the corresponding path in the destination directory
        dest_dir = os.path.expanduser(
            os.path.join(destination, os.path.relpath(dirpath, source))
        )

        # Ensure the destination directory exists
        # print('making', dest_dir)
        os.makedirs(dest_dir, exist_ok=True)

        for filename in filenames:
            if not filename.startswith("."):
                src_file = os.path.join(dirpath, filename)
                dest_file = os.path.join(dest_dir, filename)

                # Copy file if it's new or updated
                if (
                    not os.path.exists(dest_file)
                    or os.stat(src_file).st_mtime > os.stat(dest_file).st_mtime
                ):
                    created_files.append(dest_file)
                    # (f"{src_file} --> {dest_file}")
                    shutil.copy2(src_file, dest_file)

    return created_files


class MyDumper(yaml.Dumper):
    """
    A custom YAML Dumper class that increases indentation for better readability.

    Methods:
        increase_indent: Increase the indentation level in the YAML output.
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        """
        Increase the indentation level in the YAML output.

        Args:
            flow (bool): Whether to flow style indentation is used. Default is False.
            indentless (bool): Whether to use indentless indentation. Default is False.
        """
        return super(MyDumper, self).increase_indent(flow, False)


def extract_results_paths(log_entries: List[str]) -> List[str]:
    """
    Extract unique file paths ending with .jsonl from a list of log entries.

    Args:
        log_entries (List[str]): A list of log entries as strings.

    Returns:
        List[str]: A list of unique file paths ending with .jsonl extracted from the log entries.
    """
    # Regular expression to match file paths ending with .jsonl
    file_path_regex = r"/tmp/evallogs/[^ ]+\.jsonl"

    # Extract and return unique file paths
    return list(
        set(
            re.search(file_path_regex, entry).group()
            for entry in log_entries
            if re.search(file_path_regex, entry)
        )
    )


def read_save_data(
    file_path: str, db_path: str, run_kwargs_dict: Dict[str, Any] = {}
) -> None:
    """
    Process log files, extract information, and store the info in an SQLite database.

    Args:
        file_path (str): The path of the log file.
        db_path (str): The path of the SQLite database.
        run_kwargs_dict (Dict[str, Any]): Extra metadata about the completion and grader LLMs.
    """
    try:
        print("Opening", file_path)
        with open(file_path, "r") as read_file:
            data = [json.loads(line) for line in read_file]
            spec_line = None
            # final_report_line = None

            for ix, line in enumerate(data):
                if "spec" in line:
                    spec_line = ix
                if "final_report" in line:
                    final_report_line = ix

            # dumps the "arg" part in the "spec" data
            data[spec_line]["spec"]["run_config"]["eval_spec"]["args"][
                "run_kwargs"
            ] = run_kwargs_dict
            data[spec_line]["spec"]["run_config"]["eval_spec"]["args"] = json.dumps(
                data[spec_line]["spec"]["run_config"]["eval_spec"]["args"]
            )

            # flatten the "spec" data
            data_flattened = flatten(data[spec_line]["spec"], "__")
            run_metadata_df = pd.DataFrame([data_flattened])
            # process the final report data

            # # condition for rubric-graded evals
            # TODO Ignore final report for now?????
            # Rubrics will need them!
            # if "score" in data[final_report_line].get("final_report", {}):
            #     run_aggregate_score = pd.DataFrame(
            #         {
            #             "run_id": run_metadata_df["run_id"][0],
            #             # "test_name": 'rubric_of_some_kind',
            #             "role": "rubric",
            #             "metric_aggregate_value": data[final_report_line][
            #                 "final_report"
            #             ]["score"],
            #             "metric_name": run_metadata_df["base_eval"][0],
            #             "aggregation": "average",
            #         },
            #         index=[0],
            #     )
            # else:
            # test_names = list(data[final_report_line].get("final_report", {}).keys())
            # run_aggregate_score = pd.DataFrame()
            # for test_name in test_names:
            #     new_run_score_pd = pd.DataFrame(
            #         data[final_report_line]["final_report"][test_name]
            #     )  # might be more than one metric
            #     new_run_score_pd["run_id"] = run_metadata_df["run_id"][0]
            #     new_run_score_pd["role"] = "assistant"
            #     run_aggregate_score = pd.concat(
            #         [run_aggregate_score, new_run_score_pd], ignore_index=True
            #     )
            # process separate runs
            Num = len(data)
            run_single_score = pd.DataFrame()
            for i in range(1, Num):
                if i not in [spec_line, final_report_line]:
                    data[i]["data"] = json.dumps(data[i]["data"])
                    # flatten the separate run
                    run_flattened = flatten(data[i])
                    df_run = pd.DataFrame([run_flattened])
                    run_single_score = pd.concat(
                        [run_single_score, df_run], ignore_index=True
                    )
        # add unix timestamps
        run_metadata_df["created_at_ts"] = run_metadata_df["created_at"].apply(
            lambda x: int(datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f").timestamp())
        )
        run_single_score["created_at_ts"] = run_single_score["created_at"].apply(
            lambda x: int(datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f%z").timestamp())
        )
    # Convert the datetime object to a Unix timestamp and round it to the nearest whole number
    # unix_timestamp = int(date_object.timestamp())

    except Exception as err:
        print(f"An error occurred when reading the file {file_path}: {err}")
        print(traceback.print_exc())

    try:
        with sqlite3.connect(db_path) as conn:
            run_metadata_df.to_sql(
                "run_metadata", conn, index=False, if_exists="append"
            )
    except Exception as err:
        print(
            f"An error occurred when connecting to the database or saving 'run_metadata' to the database: {err}"
        )
        print(traceback.print_exc())

    # try:
    #     with sqlite3.connect(db_path) as conn:
    #         run_aggregate_score.to_sql(
    #             "run_aggregate_score", conn, index=False, if_exists="append"
    #         )
    # except Exception as err:
    #     print(
    #         f"An error occurred when connecting to the database or saving data to the database: {err}"
    #     )
    #     print(traceback.print_exc())

    try:
        with sqlite3.connect(db_path) as conn:
            run_single_score.to_sql(
                "run_single_score", conn, index=False, if_exists="append"
            )
    except Exception as err:
        print(
            f"An error occurred when connecting to the database or saving data to the database: {err}"
        )
        print(traceback.print_exc())
