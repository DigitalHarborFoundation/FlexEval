from collections import Counter

from flexeval.classes import metric


def count_dict_values(lst: list[dict]) -> dict[str, Counter]:
    """Convenience function for counting key values.

    Args:
        lst (list[dict]): List of dictionaries.

    Returns:
        dict[str, Counter]: counter for each key that appears in the dicts in lst.
    """
    counts = {}
    for d in lst:
        for k, v in d.items():
            if k not in counts:
                counts[k] = Counter()
            counts[k][v] += 1
    return counts


def get_all_metrics() -> list:
    results = []
    for m in metric.Metric.select():
        results.append(m.__data__.copy())
    return results
