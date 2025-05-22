from pathlib import Path

from pydantic import BaseModel, Field

from flexeval.schema import eval_schema


class Config(BaseModel):
    class Config:
        extra = "allow"

    rubric_metrics_path: list[Path] | Path
    # eval: eval_schema.Eval
    logs_path: Path

    env_filepath: Path | None = None
    database_path: Path = Field(
        Path("data/results/results.db"), description="Output path."
    )
    env: dict | None = Field(
        default_factory=dict, description="Any additional environment variables"
    )
    clear_tables: bool = Field(False, description="Clear any existing tables")
    max_workers: int = 1
    random_seed_conversation_sampling: int = 42
    max_n_conversation_threads: int = 50
    nb_evaluations_per_thread: int = 1
