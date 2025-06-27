import json
from typing import Iterable

from flexeval.classes.metric import Metric


def save_metrics(metrics: Iterable[Metric]):
    for metric in metrics:
        # TODO - speed this up somehow
        thread = metric.get("thread")
        if thread is None:
            thread = metric[metric["metric_level"].lower()].thread
        Metric.create(
            message=metric.get("message", None),
            turn=metric.get("turn", None),
            toolcall=metric.get("toolcall", None),
            evalsetrun=metric[
                metric["metric_level"].lower()
            ].evalsetrun,  # metric["turn"].evalsetrun,
            dataset=metric[
                metric["metric_level"].lower()
            ].dataset,  # metric["turn"].dataset,
            thread=thread,
            evaluation_name=metric["evaluation_name"],
            evaluation_type=metric["evaluation_type"],
            metric_name=metric["metric_name"],
            metric_value=metric["metric_value"],
            metric_level=metric["metric_level"],
            kwargs=metric["kwargs"],
            depends_on=json.dumps(metric["depends_on"]),
            context_only=metric.get("context_only", False),
            source=metric["source"],
            rubric_prompt=metric.get("rubric_prompt", None),
            rubric_completion=metric.get("rubric_completion", None),
            rubric_model=metric.get("rubric_model", None),
            rubric_completion_tokens=metric.get("rubric_completion_tokens", None),
            rubric_prompt_tokens=metric.get("rubric_prompt_tokens", None),
            rubric_score=metric.get("rubric_score", None),
        )
