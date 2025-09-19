"""Utilities for :mod:`~flexeval.runner`."""

import json
import logging

from flexeval import rubric
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.eval_set_run import EvalSetRun, EvalSetRunDatasets
from flexeval.schema import evalrun_schema
from flexeval import data_loader

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


def find_dataset_by_name(name: str):
    eligible_datasets = Dataset.select().where(Dataset.name == name)
    if len(eligible_datasets) == 0:
        raise ValueError(f"No dataset with name '{name}'.")
    elif len(eligible_datasets) > 1:
        raise ValueError(f"Multiple datasets with name '{name}'.")
    else:
        dataset = eligible_datasets[0]
        if not dataset.is_loaded:
            raise ValueError(
                f"Found a dataset with name '{name}', but it's not loaded into the database. This may indicate an integrity error."
            )
        return dataset


def create_dataset(data_source: evalrun_schema.DataSource) -> Dataset:
    dataset = Dataset.create(
        datasource_type=type(data_source).__name__,
        name=data_source.name,
        notes=data_source.notes,
    )
    return dataset


def load_datasets(
    evalrun: evalrun_schema.EvalRun,
) -> list[Dataset]:
    datasets = []
    for data_source in evalrun.data_sources:
        if isinstance(data_source, evalrun_schema.NamedDataSource):
            dataset = find_dataset_by_name(data_source.name)
        elif isinstance(data_source, evalrun_schema.IterableDataSource):
            dataset = create_dataset(data_source)
            data_loader.load_iterable(dataset, data_source.contents)
            dataset.is_loaded = True
            dataset.save()
        elif isinstance(data_source, evalrun_schema.FileDataSource):
            dataset = create_dataset(data_source)
            data_loader.load_file(dataset, data_source)
            dataset.metadata_dict["imported_path"] = data_source.path
            dataset.metadata_dict["imported_format"] = data_source.format
            dataset.is_loaded = True
            dataset.save()
        datasets.append(dataset)
    return datasets


def set_datasets_for_evalsetrun(datasets: list[Dataset], evalsetrun: EvalSetRun):
    for dataset in datasets:
        EvalSetRunDatasets.create(
            evalsetrun=evalsetrun,
            dataset=dataset,
        )


def build_evalsetrun_datasets(
    evalrun: evalrun_schema.EvalRun, evalsetrun: EvalSetRun
) -> list[Dataset]:
    datasets = load_datasets(evalrun)
    set_datasets_for_evalsetrun(datasets, evalsetrun)
    return datasets
