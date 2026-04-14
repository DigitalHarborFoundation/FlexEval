import json
from typing import Iterable

from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.metric import Metric


def save_metrics(
    metrics: Iterable[Metric], evalsetrun: EvalSetRun, datasets: list[Dataset]
):
    # Build a mapping from dataset id to dataset for quick lookup
    dataset_by_id = {d.id: d for d in datasets}
    for metric in metrics:
        # TODO - speed this up somehow
        thread = metric.get("thread")
        if thread is None:
            thread = metric[metric["metric_level"].lower()].thread
        # Determine the dataset from the metric's object
        metric_object = metric[metric["metric_level"].lower()]
        dataset = dataset_by_id.get(metric_object.dataset_id)
        Metric.create(
            message=metric.get("message", None),
            turn=metric.get("turn", None),
            toolcall=metric.get("toolcall", None),
            evalsetrun=evalsetrun,
            dataset=dataset,
            thread=thread,
            evaluation_name=metric["evaluation_name"],
            evaluation_type=metric["evaluation_type"],
            metric_name=metric["metric_name"],
            metric_value=metric["metric_value"],
            metric_level=metric["metric_level"],
            kwargs=metric["kwargs"],
            depends_on=json.dumps(metric["depends_on"]),
            source=metric["source"],
            rubric_prompt=metric.get("rubric_prompt", None),
            rubric_completion=metric.get("rubric_completion", None),
            rubric_model=metric.get("rubric_model", None),
            rubric_completion_tokens=metric.get("rubric_completion_tokens", None),
            rubric_prompt_tokens=metric.get("rubric_prompt_tokens", None),
            rubric_score=metric.get("rubric_score", None),
        )
