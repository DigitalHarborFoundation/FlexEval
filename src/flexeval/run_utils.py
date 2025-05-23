import json
import yaml
import logging

from flexeval import rubric
from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.dataset import Dataset


logger = logging.getLogger(__name__)


def build_eval_set_run(runner: EvalRunner) -> EvalSetRun:
    rubrics = rubric.load_rubrics_from_config(runner.config)

    # TODO this code uses a model_name that does not appear in the Eval schema; should look into this
    model_name = json.dumps(None)
    # model_name = json.dumps(
    #        runner.eval.get("completion_llm", {}).get("model_name", None)
    #    )
    evalsetrun = EvalSetRun.create(
        name=runner.eval.name,
        notes=runner.eval.notes,
        metrics=runner.eval.metrics.model_dump_json(),
        metrics_graph_ordered_list=json.dumps(runner.metrics_graph_ordered_list),
        dataset_files=runner.eval.data.model_dump_json(),
        do_completion=runner.eval.do_completion,
        completion_llm=(
            runner.eval.completion_llm.model_dump_json()
            if runner.eval.completion_llm is not None
            else json.dumps(None)
        ),
        model_name=model_name,
        grader_llm=(
            runner.eval.grader_llm.model_dump_json()
            if runner.eval.grader_llm is not None
            else json.dumps(None)
        ),
        # only save rubrics that will actually be used
        rubrics=json.dumps(
            {
                i["evaluation_name"]: rubrics[i["evaluation_name"]]
                for i in runner.metrics_graph_ordered_list
                if i["evaluation_type"] == "rubric"
            }
        ),
    )
    return evalsetrun


def build_datasets(runner: EvalRunner, evalsetrun: EvalSetRun):
    max_n_conversation_threads = runner.configuration.get(
        "max_n_conversation_threads", None
    )
    nb_evaluations_per_thread = runner.configuration.get(
        "nb_evaluations_per_thread", None
    )
    for filename in evalsetrun.get_datasets():
        # these will automatically be saved as a property of evalsetrun
        Dataset.create(
            evalsetrun=evalsetrun,
            filename=filename,
            max_n_conversation_threads=max_n_conversation_threads,
            nb_evaluations_per_thread=nb_evaluations_per_thread,
        )
        runner.logger.info(
            f"Created dataset from {filename}. Max number of conversation threads: {max_n_conversation_threads} - Nb of evaluations per thread: {nb_evaluations_per_thread}"
        )
