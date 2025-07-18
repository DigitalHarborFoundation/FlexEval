from pathlib import Path

from pydantic import BaseModel, Field

from flexeval.schema import schema_utils


class Config(BaseModel):
    class Config:
        extra = "ignore"
        # validate_assignment will ensure that fields never take an invalid value e.g. if copied from an eval
        validate_assignment = True

    logs_path: Path | None = Field(
        None,
        description="Log directory path.",
    )
    env_filepath: Path | None = Field(
        None,
        description="A .env file to be processed by python-dotenv before running evals with this config.",
    )
    env: schema_utils.OptionalDict = Field(
        default_factory=dict, description="Any additional environment variables."
    )
    clear_tables: bool = Field(
        False,
        description="Clear any existing tables, if the output SQLite database already exists.",
    )
    max_workers: int = Field(
        1,
        description="Max worker count. Multiple threads will be used if set to > 1. This may have usage limit implications if you are calling APIs.",
    )
    random_seed_conversation_sampling: int = 42
    max_n_conversation_threads: int = (
        50  # TODO allow setting this to None, and set it to None by default
    )
    nb_evaluations_per_thread: int = 1

    raise_on_completion_error: bool = Field(
        False,
        description="If False (default), metrics will be run even if one or more completions fails.",
    )
    raise_on_metric_error: bool = Field(
        False,
        description="If False (default), no exception will be thrown if a metric function raises an exception.",
    )
