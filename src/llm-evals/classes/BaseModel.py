import os

import peewee as pw
from playhouse.sqliteq import SqliteQueueDatabase


class BaseModel(pw.Model):
    """Class for handling databaset setup, etc."""

    class Meta:
        # will hold database connection
        pass

    @classmethod
    def initialize_database(cls):
        database_path = os.environ.get("DATABASE_PATH")
        if database_path:
            database = SqliteQueueDatabase(
                database_path,
                use_gevent=False,  # Use the standard library "threading" module.
                queue_max_size=64,  # Max. # of pending writes that can accumulate.
                results_timeout=5.0,
            )
            cls._meta.database = database
        else:
            raise ValueError("Database path must be set in the environment variables")
