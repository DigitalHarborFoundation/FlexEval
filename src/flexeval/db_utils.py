"""Peewee database utilities."""

import peewee as pw

from flexeval.classes import base as classes_base
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.message import Message
from flexeval.classes.metric import Metric
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn

DATABASE_TABLES = [EvalSetRun, Dataset, Thread, Turn, Message, ToolCall, Metric]


def ensure_database(database_path: str):
    if not classes_base.database.is_connection_usable():
        initialize_database(database_path)


def initialize_database(database_path: str, clear_tables: bool = False):
    classes_base.database.init(database_path)
    # classes_base.database.start()

    if clear_tables:
        classes_base.database.drop_tables(DATABASE_TABLES)
    classes_base.database.create_tables(DATABASE_TABLES)


def bind_to_database(database_path: str) -> pw.Database:
    """Utility function for binding to a FlexEval database so that ORM functionality can be used.

    See: https://docs.peewee-orm.com/en/latest/peewee/database.html#setting-the-database-at-run-time

    Returns:
        pw.Database: The new database created for the models to bind to.
    """
    new_database = classes_base.create_sqlite_database(database_path)
    new_database.bind(DATABASE_TABLES)
    # Verify the binding worked by checking one of the models
    assert classes_base.BaseModel._meta.database == new_database, (
        f"Binding to '{database_path}' failed."
    )
    return new_database
