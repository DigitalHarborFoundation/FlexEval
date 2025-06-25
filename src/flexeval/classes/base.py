import peewee as pw
from playhouse.sqliteq import SqliteQueueDatabase


class BaseModel(pw.Model):
    """Class for handling databaset setup, etc."""

    class Meta:
        # will hold database connection
        pass

    @classmethod
    def set_database_path(cls: "BaseModel", database_path: str) -> pw.Database:
        database = SqliteQueueDatabase(
            database_path,
            use_gevent=False,  # Use the standard library "threading" module.
            queue_max_size=64,  # Max. # of pending writes that can accumulate.
            results_timeout=5.0,
        )
        cls._meta.database = database
        database.connect()
        return database

    @classmethod
    def initialize_database(
        cls: "BaseModel", database_path: str, clear_table: bool = False
    ):
        database = cls.set_database_path(database_path)
        if clear_table:
            database.drop_tables([cls])
        database.create_tables([cls], safe=False)
