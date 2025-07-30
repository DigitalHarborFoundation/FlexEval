import logging
from pathlib import Path
from typing import Type, TypeVar

import pydantic
import yaml

from flexeval.schema import Config, Eval, EvalRun

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=pydantic.BaseModel)


def load_config_from_yaml(
    filename: Path | str,
) -> Config:
    return load_model_from_yaml(filename, Config)


def load_evals_from_yaml(
    filename: Path | str,
) -> dict[str, Eval]:
    return load_models_from_yaml_filepath(filename, Eval)


def load_eval_run_from_yaml(
    filename: Path | str,
) -> EvalRun:
    return load_model_from_yaml(filename, EvalRun)


def load_models_from_yaml_filepath(
    filename: Path | str,
    model_type: Type[T],
) -> dict[str, T]:
    try:
        with open(filename) as file:
            return load_models_from_yaml_stream(file, model_type)
    except (OSError, ValueError) as ex:
        raise ValueError(
            f"Failed to load '{filename}' as a list of '{model_type.__name__}' models: {ex}"
        )


def load_models_from_yaml_stream(
    stream,
    model_type: Type[T],
) -> dict[str, T]:
    try:
        contents = yaml.safe_load(stream)
        return {key: model_type(**value) for key, value in contents.items()}
    except (OSError, yaml.YAMLError, pydantic.ValidationError) as ex:
        raise ValueError(
            f"Failed to load YAML stream as a list of '{model_type.__name__}' models: {ex}"
        )


def load_model_from_yaml(
    filename: Path | str,
    model_type: Type[T],
) -> T:
    try:
        with open(filename) as file:
            contents = yaml.safe_load(file)
            return model_type(**contents)
    except (OSError, yaml.YAMLError, pydantic.ValidationError) as ex:
        raise ValueError(
            f"Failed to load '{filename}' as a '{model_type.__name__}': {ex}"
        )
