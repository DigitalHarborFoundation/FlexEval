from flexeval.classes import metric


def get_all_metrics() -> list:
    results = []
    for m in metric.Metric.select():
        results.append(m.__data__.copy())
    return results
