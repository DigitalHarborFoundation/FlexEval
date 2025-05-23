from pathlib import Path

from pydantic import BaseModel, Field

from flexeval.schema import eval_schema, schema_utils


class Config(BaseModel):
    class Config:
        extra = "ignore"
        # validate_assignment will ensure that fields never take an invalid value e.g. if copied from an eval
        validate_assignment = True

    # TODO replace rubrics with Pydantic models
    # TODO consider moving rubrics to Eval
    rubric_metrics_path: list[Path] | Path = Field(
        Path("src/flexeval/configuration/rubric_metrics.yaml"),
        description="Path to a rubric metrics YAML file.",
    )
    # eval: eval_schema.Eval
    logs_path: Path | None = Field(
        None,
        description="Log directory path.",
    )
    include_default_functions: bool = True
    function_modules: list[str | schema_utils.ModuleType] | None = Field(
        None,
        description="List of filepaths or Python modules to include as function modules.",
    )
    env_filepath: Path | None = Field(
        None,
        description="A .env file to be processed by python-dotenv before running evals with this config.",
    )
    database_path: Path = Field(
        Path("flexeval/results/results.db"),
        description="Evaluation outputs database path.",
    )
    env: schema_utils.OptionalDict = Field(
        default_factory=dict, description="Any additional environment variables."
    )
    clear_tables: bool = Field(False, description="Clear any existing tables")
    max_workers: int = 1
    random_seed_conversation_sampling: int = 42
    max_n_conversation_threads: int = 50
    nb_evaluations_per_thread: int = 1
