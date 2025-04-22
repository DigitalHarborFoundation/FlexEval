import json
import yaml
import logging

from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.dataset import Dataset


logger = logging.getLogger(__name__)


def get_rubrics(runner: EvalRunner) -> dict:
    rubrics = {}
    for rf in runner.configuration["rubric_metrics_path"]:
        logger.debug("Found rubric file: %s", rf)
        with open(rf) as file:
            new_rubrics = yaml.safe_load(file)
            for key, value in new_rubrics.items():
                if key not in rubrics:
                    rubrics[key] = value
    logger.debug("Loaded rubrics: %s", rubrics)
    return rubrics


def build_eval_set_run(runner: EvalRunner, clear_tables: bool = False) -> EvalSetRun:
    rubrics = get_rubrics(runner)
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
    return evalsetrun


def build_datasets(runner: EvalRunner, evalsetrun: EvalSetRun):
    max_n_conversation_threads = runner.configuration.get(
        "max_n_conversation_threads", None
    )
    for filename in evalsetrun.get_datasets():
        # these will automatically be saved as a property of evalsetrun
        Dataset.create(
            evalsetrun=evalsetrun,
            filename=filename,
            max_n_conversation_threads=max_n_conversation_threads,
        )
        runner.logger.info(
            f"Created dataset from {filename}. Max number of conversation threads: {max_n_conversation_threads}"
        )
