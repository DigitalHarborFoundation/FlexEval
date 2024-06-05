import argparse
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

import json
from classes.EvalRunner import EvalRunner
from classes.EvalSetRun import EvalSetRun
from classes.Dataset import Dataset
from classes.DatasetRow import DatasetRow
from classes.Turn import Turn
from classes.TurnMetric import TurnMetric, compute_metric
import dotenv

dotenv.load_dotenv(".env")

# Features to add:
# - compute metrics for LAGGED inputs
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
    with open(runner.configuration["rubric_metrics_path"]) as file:
        rubrics = yaml.safe_load(file)
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
            rubrics=json.dumps(rubrics),
        )
        evalsetrun.create_metrics_graph()
        runner.logger.info(evalsetrun.metric_graph_text)
    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)
        raise e

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

                    # some turns have tool calls, in which case the content
                    # is actually a list of dicts
                    content = ""
                    for i in turn["turn"]:
                        c = i.get("content", "")
                        if isinstance(c, str):
                            content += f"\n{c}"
                        elif isinstance(c, list):
                            for entry in c:
                                c2 = entry.get("content", "")
                                if isinstance(c, str):
                                    content += f"\n{c2}"

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
        arg_list = []
        for turn in turns_to_evaluate:
            for metric_type in ["function", "rubric"]:
                for target_metric in json.loads(evalsetrun.metrics).get(
                    metric_type, []
                ):
                    arg_list.append(
                        {
                            "metric_name": target_metric.get("name", None),
                            "metric_definition": target_metric,
                            "turn": turn,
                            "metric_type": metric_type,
                        }
                    )

        runner.logger.info(
            f"Metrics will include {len([arg for arg in arg_list if arg['metric_type'] == 'rubric'])} rubric evaluations."
        )
        if n_workers == 1:
            metrics = []
            for arg in arg_list:
                metric = compute_metric(**arg)
                for m in metric:
                    if m.get("type", None) is None:
                        runner.logger.exception(
                            f"Metric {m} does not have a value for the key `type`."
                        )
                    if m.get("value", None) is None:
                        runner.logger.exception(
                            f"Metric {m} does not have a value for the key `value`."
                        )
                metrics += metric
        else:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = []
                for arg in arg_list:
                    futures.append(executor.submit(compute_metric, **arg))

                # Wait for all futures to complete and handle exceptions
                for future in futures:
                    try:
                        future.result()  # If you need to catch exceptions or ensure completion
                    except Exception as e:
                        runner.logger.exception("An error occurred during processing")
                metrics = []
                for future in futures:
                    metrics += future.result()

        runner.logger.info(f"Saving metrics to database.")
        for metric in metrics:
            # TODO - speed this up somehow
            TurnMetric.create(
                turn=metric["turn"],
                evalsetrun=metric["turn"].evalsetrun,
                dataset=metric["turn"].dataset,
                datasetrow=metric["turn"].datasetrow,
                definition=json.dumps(metric["definition"]),
                function_name=metric["function_name"],
                name=metric["name"],
                type=metric["type"],
                value=metric["value"],
                kwargs=metric["kwargs"],
                source=metric["source"],
                rubric_completion=metric.get("rubric_completion", None),
                rubric_model=metric.get("rubric_model", None),
                rubric_completion_tokens=metric.get("rubric_completion_tokens", None),
                rubric_prompt_tokens=metric.get("rubric_prompt_tokens", None),
                rubric_score=metric.get("rubric_score", None),
            )

    except Exception as e:
        runner.logger.exception("An error occurred", exc_info=True)

    runner.logger.info(f"Evaluation run complete.")
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
