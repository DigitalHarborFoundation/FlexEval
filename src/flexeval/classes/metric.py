import peewee as pw

from flexeval.classes.base import BaseModel
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.message import Message
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn


class Metric(BaseModel):
    """Holds a single metric/property computed based one just ONE turn"""

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="metrics_list")
    dataset = pw.ForeignKeyField(Dataset, backref="metrics_list")
    thread = pw.ForeignKeyField(Thread, backref="metrics_list")
    turn = pw.ForeignKeyField(
        Turn, null=True, backref="metrics_list"
    )  # Only defined for Turn metrics
    message = pw.ForeignKeyField(
        Message, null=True, backref="metrics_list"
    )  # Only defined for Message metrics
    toolcall = pw.ForeignKeyField(
        ToolCall, null=True, backref="metrics_list"
    )  # Only defined for ToolCall metrics

    evaluation_name = pw.TextField()
    evaluation_type = pw.TextField()
    metric_name = pw.TextField()
    # metric_type = pw.TextField() # TODO: Some parts of the code use "metric_tye" and others use "evaluation_type" - choose one for consistency
    metric_level = pw.TextField()
    # TODO we may want to consider adding a secondary metric_nonnumeric_value field to support non-numeric functions and rubrics
    metric_value = pw.FloatField(
        null=True
    )  # necessary if rubric result is INVALID or e.g. latency doesn't apply to the very first message
    kwargs = pw.TextField()
    source = pw.TextField()  # TODO - make another table for this? But maybe not, because this also contains filled-in rubrics
    depends_on = pw.TextField()
    rubric_prompt = pw.TextField(null=True)
    rubric_completion = pw.TextField(null=True)
    rubric_model = pw.TextField(null=True)
    rubric_completion_tokens = pw.IntegerField(null=True)
    rubric_prompt_tokens = pw.IntegerField(null=True)
    rubric_score = pw.TextField(null=True)
