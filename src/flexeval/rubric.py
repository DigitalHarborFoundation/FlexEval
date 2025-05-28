import yaml
import logging
import importlib.resources

import flexeval.configuration
from flexeval.schema import Config, Rubric
from flexeval.io.parsers import yaml_parser


logger = logging.getLogger(__name__)


default_rubric_metrics = {}  # don't access directly, use load_default_rubric_metrics


def load_rubrics_from_yaml_stream(
    stream,
) -> dict[str, Rubric]:
    return yaml_parser.load_models_from_yaml_stream(stream, Rubric)


def load_default_rubric_metrics():
    global default_rubric_metrics
    if len(default_rubric_metrics) > 0:
        return default_rubric_metrics
    logger.debug(f"Loading rubric_metrics.yaml")
    metrics_path = (
        importlib.resources.files(flexeval.configuration) / "rubric_metrics.yaml"
    )
    metrics_string = metrics_path.read_text()
    default_rubric_metrics = load_rubrics_from_yaml_stream(metrics_string)
    return default_rubric_metrics


def load_rubric_from_yaml(rubric_path: str):
    with open(rubric_path) as file:
        rubric = yaml.safe_load(file)
    return rubric


def load_rubrics_from_config(config: Config) -> dict:
    rubric_metrics = {}
    rubric_metrics_paths = (
        config.rubric_metrics_path
        if isinstance(config.rubric_metrics_path, list)
        else [config.rubric_metrics_path]
    )
    for rf in rubric_metrics_paths:
        with open(rf) as file:
            new_rubrics = yaml.safe_load(file)
            logger.debug("New rubric: %s", new_rubrics)
            for key, value in new_rubrics.items():
                if key not in rubric_metrics:
                    rubric_metrics[key] = value
                else:
                    logger.warning(
                        f"Ignoring second (or later) version of rubric '{key}'."
                    )
    return rubric_metrics
