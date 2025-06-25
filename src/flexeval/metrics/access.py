from pathlib import Path

from flexeval.schema import evalrun_schema
from flexeval.classes import metric


def get_all_metrics(database_path: Path) -> list:
    metric.Metric.set_database_path(str(database_path))
    results = []
    for m in metric.Metric.select():
        results.append(m.__data__.copy())
    return results
