from flexeval.schema import Config
import yaml
import logging

logger = logging.getLogger(__name__)


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
