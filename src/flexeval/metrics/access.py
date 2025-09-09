"""Utility functions for accessing metrics."""

from collections import Counter

from flexeval.classes import metric, message, turn, thread


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


def get_all_metrics() -> list[dict]:
    results = []
    for m in metric.Metric.select():
        results.append(m.__data__.copy())
    return results


def get_first_user_message_for_threads(thread_ids: set) -> list[dict]:
    """Get the first user message in each thread.

    Args:
        thread_ids (set): The set of thread IDs to retrieve messages for.

    Returns:
        list[dict]: An iterable of messages.
    """
    return (
        message.Message.select()
        .join(thread.Thread)
        .where(thread.Thread.id.in_(thread_ids))
        .where(message.Message.role == "user")
        .join(turn.Turn)
        .where(turn.Turn.index_in_thread == 0)
        .dicts()
    )
