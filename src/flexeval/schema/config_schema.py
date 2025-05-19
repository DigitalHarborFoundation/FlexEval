from pathlib import Path

from pydantic import BaseModel, Field

from flexeval.schema import eval_schema


class Config(BaseModel):
    rubric_metrics_paths: list[Path]
    eval: eval_schema.Eval
    env_filepath: Path
    logs_path: Path
    database_path: Path = Field(
        Path("data/results/results.db"), description="Output path."
    )
    env: dict = Field({}, description="Any additional environment variables")
    max_workers: int = 1
    random_seed_conversation_sampling: int = 42
    max_n_conversation_threads: int = 50
    nb_evaluations_per_thread: int = 1
