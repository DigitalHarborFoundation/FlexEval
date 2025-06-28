import json
from datetime import datetime

import peewee as pw

from flexeval.classes.base import BaseModel


class EvalSetRun(BaseModel):
    """Class for running set of evaluations"""

    id = pw.IntegerField(primary_key=True)
    name = pw.CharField(null=True)
    notes = pw.TextField(null=True)
    dataset_files = pw.TextField()  # JSON string
    metrics = pw.TextField()
    metrics_graph_ordered_list = pw.TextField()
    do_completion = pw.BooleanField()
    completion_llm = pw.TextField(null=True)  # JSON string
    grader_llm = pw.TextField(null=True)  # JSON string
    model_name = pw.TextField(null=True)  # JSON string
    success = pw.BooleanField(null=True)
    rubrics = pw.TextField(null=True)
    timestamp = pw.DateTimeField(
        default=datetime.now
    )  # Automatically set to current date and time

    def get_datasets(self) -> list[str]:
        # TODO Turn these into DataSource instances instead, returning list[DataSource]
        temp = json.loads(self.dataset_files)
        assert isinstance(temp, list), "The `data` entry in evals.yaml must be a list."
        return temp
