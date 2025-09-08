"""The top-level :class:`~flexeval.schema.evalrun_schema.EvalRun` schema and associated sub-schema."""

from pathlib import Path
from typing import Annotated, Callable, Iterable, Literal

from annotated_types import Len
from pydantic import BaseModel, Field, FilePath

from flexeval.configuration import function_metrics
from flexeval.schema import config_schema, eval_schema, rubric_schema, schema_utils


class DataSource(BaseModel):
    # TODO support more generic DataSource interface
    # for now, we need to use FileDataSource because we path the JSONL paths along
    name: str | None = Field(None, description="")
    notes: str | None = Field(None, description="")


class IterableDataSource(DataSource):
    """Not yet implemented."""

    contents: Iterable = Field(
        default_factory=list,
        description="Iterable of data items, presumably in the jsonl format (for now).",
    )


class FileDataSource(DataSource):
    """File to be used as a data source."""

    # TODO in the future, we could use cloudpathlib to support cloud paths
    path: FilePath = Field(
        description="Absolute or relative path to data file. Each file must be in jsonl format, with one conversation per line."
    )
    format: Literal["jsonl"] = Field("jsonl", description="Format of the data file.")


class FunctionsCollection(BaseModel):
    """Collection of functions that can be used as :class:`~flexeval.schema.eval_schema.FunctionItem` s."""

    functions: list[Callable] = Field(
        default_factory=list,
        description="Callables that can be used as functions for evaluation.",
    )


def get_default_rubrics() -> list[Path | rubric_schema.RubricsCollection]:
    """Utility function to retrieve the default rubric collection."""
    from flexeval import rubric

    return [rubric.get_default_rubric_collection()]


def get_default_function_metrics() -> list[
    Path | FunctionsCollection | schema_utils.ModuleType
]:
    """Utility function to retrieve the default function collection."""
    return [function_metrics]


class EvalRun(BaseModel):
    """EvalRun defines the schema that FlexEval expects.

    At a minimum, you need to provide a set of input data sources and an :class:`~flexeval.schema.eval_schema.Eval`.

    You can evaluate an EvalRun using :func:`~flexeval.runner.run`.

    Read more in the :ref:`user_guide`."""

    data_sources: Annotated[list[FileDataSource], Len(min_length=1)] = Field(
        description="List of data sources.",
    )
    database_path: Path = Field(
        Path("flexeval/results/results.db"),
        description="Output database path.",
    )
    eval: eval_schema.Eval = Field(
        description="The evaluation to apply to the data sources."
    )
    config: config_schema.Config = Field(
        default_factory=config_schema.Config, description="Configuration details."
    )
    rubric_paths: list[Path | rubric_schema.RubricsCollection] = Field(
        default_factory=get_default_rubrics,
        description="Additional sources for rubrics. If a Path, should be a YAML file in the expected format.",
    )
    function_modules: list[FilePath | FunctionsCollection | schema_utils.ModuleType] = (
        Field(
            default_factory=get_default_function_metrics,
            description="Additional sources for functions.",
        )
    )
    add_default_functions: bool = Field(
        True,
        description="If the default functions at :mod:`flexeval.configuration.function_metrics` should be made available.",
    )
