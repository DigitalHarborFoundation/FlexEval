"""Rubric metric IO utilities. Should maybe be moved to :mod:`~flexeval.io`."""

import importlib.resources
import logging
from pathlib import Path

import flexeval.configuration
from flexeval.io.parsers import yaml_parser
from flexeval.schema import Rubric, RubricsCollection

logger = logging.getLogger(__name__)


default_rubric_collection = (
    None  # don't access directly, use load_default_rubric_metrics
)


def load_rubrics_from_yaml_file(path: Path) -> dict[str, Rubric]:
    return yaml_parser.load_models_from_yaml_filepath(path, Rubric)


def load_rubrics_from_yaml_stream(
    stream,
) -> dict[str, Rubric]:
    return yaml_parser.load_models_from_yaml_stream(stream, Rubric)


def get_default_rubric_collection() -> RubricsCollection:
    global default_rubric_collection
    if default_rubric_collection is not None:
        return default_rubric_collection
    logger.debug("Attempting to load from default rubric_metrics.yaml.")
    metrics_path = (
        importlib.resources.files(flexeval.configuration) / "rubric_metrics.yaml"
    )
    metrics_string = metrics_path.read_text()
    rubric_metrics = load_rubrics_from_yaml_stream(metrics_string)
    default_rubric_collection = RubricsCollection(rubrics=rubric_metrics)
    return default_rubric_collection


def load_rubric_metrics(
    rubric_collections: list[Path | RubricsCollection], add_defaults: bool = False
) -> dict[str, Rubric]:
    rubric_metrics = {}
    if add_defaults:
        rubric_collections.append(get_default_rubric_collection())
    for rubric_collection in rubric_collections:
        if isinstance(rubric_collection, Path):
            rubric_dict = load_rubrics_from_yaml_file(rubric_collection)
        else:
            rubric_dict = rubric_collection.rubrics
        for key, rubric in rubric_dict.items():
            if key not in rubric_metrics:
                rubric_metrics[key] = rubric
                if rubric.name is None:
                    # infer rubric name from parent key
                    rubric.name = key
            else:
                logger.warning(f"Ignoring second (or later) version of rubric '{key}'.")
    return rubric_metrics
