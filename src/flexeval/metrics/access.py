from collections import Counter

from flexeval.classes import metric


def count_dict_values(l: list[dict]) -> dict[str, Counter]:
    """Convenience function for counting key values.

    Args:
        l (list[dict]): List of dictionaries.

    Returns:
        dict[str, Counter]: counter for each key that appears in the dicts in l.
    """
    counts = {}
    for d in l:
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
