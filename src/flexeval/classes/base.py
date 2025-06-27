import peewee as pw
from playhouse.shortcuts import ThreadSafeDatabaseMetadata
from playhouse.sqliteq import SqliteQueueDatabase


def create_sqlite_database(
    database_path: str | None = None, use_queue_db: bool = False
) -> pw.SqliteDatabase:
    if use_queue_db:
        return SqliteQueueDatabase(
            database_path,
            use_gevent=False,
            autostart=False,
            results_timeout=5.0,
            queue_max_size=64,  # Max. # of pending writes that can accumulate
            pragmas={"journal_mode": "wal"},  # use Write-ahead Logging
        )
    return pw.SqliteDatabase(
        database_path,
        pragmas={"journal_mode": "wal"},  # use Write-ahead Logging
    )


database = create_sqlite_database()


class BaseModel(pw.Model):
    """Peewee base class for all FlexEval database models."""

    class Meta:
        model_metadata_class = ThreadSafeDatabaseMetadata
        database = database
