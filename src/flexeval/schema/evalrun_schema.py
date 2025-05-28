import importlib.resources
from pathlib import Path
from typing import Annotated, Callable, Iterable, Literal

from annotated_types import Len
from pydantic import BaseModel, Field, FilePath, AfterValidator

import flexeval.configuration
from flexeval.configuration import function_metrics
from flexeval.schema import config_schema, eval_schema, schema_utils, rubric_schema


class DataSource(BaseModel):
    name: str | None = Field(None, description="")
    notes: str | None = Field(None, description="")


class IterableDataSource(DataSource):
    contents: Iterable = Field(
        default_factory=list,
        description="Iterable of data items, presumably in the jsonl format (for now).",
    )


class FileDataSource(DataSource):
    # TODO in the future, we could use cloudpathlib to support cloud paths
    path: FilePath = Field(
        description="Absolute or relative path to data file. Each file must be in *.jsonl format, with one conversation per line."
    )
    format: Literal["jsonl"] = Field("jsonl", description="Format of the data file.")


class FunctionsCollection(BaseModel):
    functions: list[Callable] = Field(
        default_factory=list,
        description="Callables that can be used as functions for evaluation.",
    )


class EvalRun(BaseModel):
    data_sources: Annotated[list[DataSource], Len(min_length=1)] = Field(
        default_factory=list,
        description="List of data sources.",
    )
    database_path: Path = Field(
        Path("flexeval/results/results.db"),
        description="Output database path.",
    )
    eval: eval_schema.Eval
    config: config_schema.Config
    # FIXME: this approach for getting the rubric_metrics is cheating,
    # as it returns a Traversable and not a Path if the source is a ZIP file (for example)
    # We should instead load the defaults into a cached RubricsCollection (using importlib.resoruces.files.read_text())
    rubric_paths: list[Path | rubric_schema.RubricsCollection] = Field(
        [importlib.resources.files(flexeval.configuration) / "rubric_metrics.yaml"],
        description="Additional sources for rubrics. If a Path, should be a YAML file in the expected format.",
    )
    function_modules: list[Path | FunctionsCollection | schema_utils.ModuleType] = (
        Field([function_metrics], description="Additional sources for functions.")
    )
