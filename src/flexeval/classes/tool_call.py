import peewee as pw

from flexeval.classes.base import BaseModel
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.message import Message
from flexeval.classes.thread import Thread
from flexeval.classes.turn import Turn


class ToolCall(BaseModel):
    """Holds a single component of a single turn
    Corresponds to one output of a node in LangGraph
    or one Turn in jsonl
    """

    id = pw.IntegerField(primary_key=True)

    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="toolcalls")
    dataset = pw.ForeignKeyField(Dataset, backref="toolcalls")
    thread = pw.ForeignKeyField(Thread, backref="toolcalls")
    message = pw.ForeignKeyField(Message, backref="toolcalls")
    turn = pw.ForeignKeyField(Turn, backref="toolcalls")

    function_name = pw.TextField()
    args = pw.TextField()
    additional_kwargs = (
        pw.TextField()
    )  # holds any additional info we want to save with a tool call
    tool_call_id = pw.TextField()
    response_content = pw.TextField()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics_to_evaluate = []

    def get_dict_representation(self) -> dict:
        """
        Get a dictionary representation of the content of this toolcall,
        suitable for passing to function metrics that need a standard Python
        data structure representation of a tool call.

        Keys in returned dictionary are role, content (for the response content),
        function_name, and args.
        """
        return {
            "role": "toolcall",
            "content": self.response_content,
            "args": self.args,
            "function_name": self.function_name,
        }
