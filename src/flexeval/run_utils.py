"""Utilities for :mod:`~flexeval.runner`."""

import json
import logging

from flexeval import rubric
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.eval_set_run import EvalSetRun

logger = logging.getLogger(__name__)


def build_eval_set_run(runner: EvalRunner) -> EvalSetRun:
    rubrics = rubric.load_rubric_metrics(runner.evalrun.rubric_paths)

    # TODO this code uses a model_name that does not appear in the Eval schema; should look into this
    model_name = json.dumps(None)
    # model_name = json.dumps(
    #        runner.eval.get("completion_llm", {}).get("model_name", None)
    #    )
    evalsetrun = EvalSetRun.create(
        name=runner.evalrun.eval.name,
        notes=runner.evalrun.eval.notes,
        metrics=runner.evalrun.eval.metrics.model_dump_json(),
        metrics_graph_ordered_list=json.dumps(runner.metrics_graph_ordered_list),
        dataset_files=json.dumps(
            [str(data_source.path) for data_source in runner.evalrun.data_sources]
        ),
        do_completion=runner.evalrun.eval.do_completion,
        completion_llm=(
            runner.evalrun.eval.completion_llm.model_dump_json()
            if runner.evalrun.eval.completion_llm is not None
            else json.dumps(None)
        ),
        model_name=model_name,
        grader_llm=(
            runner.evalrun.eval.grader_llm.model_dump_json()
            if runner.evalrun.eval.grader_llm is not None
            else json.dumps(None)
        ),
        # only save rubrics that will actually be used
        rubrics=json.dumps(
            {
                i["evaluation_name"]: rubrics[i["evaluation_name"]].model_dump()
                for i in runner.metrics_graph_ordered_list
                if i["evaluation_type"] == "rubric"
            }
        ),
    )
    return evalsetrun


def build_datasets(runner: EvalRunner, evalsetrun: EvalSetRun):
    for filename in evalsetrun.get_datasets():
        # these will automatically be saved as a property of evalsetrun
        Dataset.create(
            evalsetrun=evalsetrun,
            filename=filename,
            max_n_conversation_threads=runner.evalrun.config.max_n_conversation_threads,
            nb_evaluations_per_thread=runner.evalrun.config.nb_evaluations_per_thread,
        )
        runner.logger.info(
            f"Created dataset from '{filename}'. Max number of conversation threads: '{runner.evalrun.config.max_n_conversation_threads}' - Nb of evaluations per thread: '{runner.evalrun.config.nb_evaluations_per_thread}'"
        )
