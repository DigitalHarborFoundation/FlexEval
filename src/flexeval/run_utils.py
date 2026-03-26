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
    evalsetrun = EvalSetRun.create(
        name=runner.evalrun.eval.name,
        notes=runner.evalrun.eval.notes,
        metrics=runner.evalrun.eval.metrics.model_dump_json(),
        metrics_graph_ordered_list=json.dumps(runner.metrics_graph_ordered_list),
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


def find_dataset_by_name(name: str) -> Dataset:
    eligible_datasets = Dataset.select().where(Dataset.name == name)
    if len(eligible_datasets) == 0:
        raise ValueError(f"No dataset with name '{name}'.")
    elif len(eligible_datasets) > 1:
        raise ValueError(f"Multiple datasets with name '{name}'.")
    else:
        dataset = eligible_datasets.first()
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
    config = evalrun.config
    for data_source in evalrun.data_sources:
        datasource_type = type(data_source).__name__

        # 1. Validate naming constraints
        if config.raise_on_unnamed_dataset and (
            data_source.name is None or data_source.name.strip() == ""
        ):
            raise ValueError(
                f"Configuration requires named datasets, but a {datasource_type} was unnamed."
            )

        # 2. Look up existing dataset by name (if named)
        existing_dataset = None
        if data_source.name:
            try:
                existing_dataset = find_dataset_by_name(data_source.name)
            except ValueError:
                existing_dataset = None

        # 3. Dispatch by DataSource type
        if isinstance(data_source, evalrun_schema.NamedDataSource):
            # NamedDataSource MUST match an existing dataset
            if existing_dataset is None:
                raise ValueError(
                    f"NamedDataSource requires an existing dataset with name '{data_source.name}', but none was found."
                )
            dataset = existing_dataset

        elif isinstance(
            data_source,
            (evalrun_schema.FileDataSource, evalrun_schema.IterableDataSource),
        ):
            # Check for duplicate name conflict
            if config.raise_on_duplicate_dataset_name and existing_dataset is not None:
                raise ValueError(
                    f"Configuration requires unique dataset names, but '{data_source.name}' already exists (ID={existing_dataset.id})."
                )

            # Reuse if configured and existing dataset matches
            if config.reuse_dataset_by_name and existing_dataset is not None:
                if existing_dataset.datasource_type != datasource_type:
                    logger.warning(
                        f"Reusing dataset '{existing_dataset.name}' (ID={existing_dataset.id}) "
                        f"but datasource type differs: existing={existing_dataset.datasource_type}, new={datasource_type}."
                    )
                logger.info(
                    f"Reusing existing dataset '{existing_dataset.name}' (ID={existing_dataset.id})."
                )
                dataset = existing_dataset
            else:
                # Create and load new dataset
                dataset = create_dataset(data_source)
                if isinstance(data_source, evalrun_schema.IterableDataSource):
                    data_loader.load_iterable(dataset, data_source.contents)
                elif isinstance(data_source, evalrun_schema.FileDataSource):
                    data_loader.load_file(
                        dataset,
                        data_source,
                        max_n_conversation_threads=config.max_n_conversation_threads,
                        nb_evaluations_per_thread=config.nb_evaluations_per_thread,
                    )
                    dataset.metadata_dict["imported_path"] = str(data_source.path)
                    dataset.metadata_dict["imported_format"] = data_source.format.value
                dataset.is_loaded = True
                dataset.save()
        else:
            raise ValueError(f"Unsupported DataSource type: {datasource_type}")

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
