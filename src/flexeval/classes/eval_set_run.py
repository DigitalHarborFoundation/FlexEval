from datetime import datetime

import peewee as pw

from flexeval.classes.base import BaseModel
from flexeval.classes.dataset import Dataset


class EvalSetRun(BaseModel):
    """Class for running set of evaluations"""

    id = pw.IntegerField(primary_key=True)
    name = pw.CharField(null=True)
    notes = pw.TextField(null=True)
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


class EvalSetRunDatasets(BaseModel):
    """Datasets used by an EvalSetRun."""

    id = pw.IntegerField(primary_key=True)
    timestamp = pw.DateTimeField(default=datetime.now)
    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="datasets")
    dataset = pw.ForeignKeyField(Dataset, backref="evalsetruns")
