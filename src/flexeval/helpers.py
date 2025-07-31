"""Generic utility functions."""

import datetime
import hashlib

import networkx as nx


def generate_hash():
    """Create a random 8-digit id"""
    # Create a new SHA-256 hash object
    hash_object = hashlib.sha256()

    # Update the hash object with the bytes of the string
    hash_object.update(datetime.datetime.now().isoformat().encode())

    # Get the hexadecimal digest of the hash
    full_hash = hash_object.hexdigest()

    # Return the first 8 digits of the hash
    return full_hash[:8]


def visualize_graph(graph: nx.DiGraph, output_path: str | None = None):
    """Visualize graphs produced by :class:`~flexeval.compute_metrics.MetricGraphBuilder`.

    Args:
        graph (nx.DiGraph): The graph
        output_path (str | None, optional): If not None, will save the graph as an image using :meth:`matplotlib.pyplot.Figure.savefig`.

    Raises:
        ImportError: If matplotlib is not installed.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib must be installed to use this helper function.")
    fig, ax = plt.subplots(1, 1, figsize=(12, 5))
    pos = nx.spring_layout(graph)
    nx.draw(graph, ax=ax, pos=pos)
    nx.draw_networkx_labels(
        graph,
        font_size=8,
        ax=ax,
        pos=pos,
        labels={
            om: f"{om.object.__class__.__name__} {om.object.id}\n{om.metric.get('id')}(l={om.metric.get('metric_level')},r={om.metric.get('kwargs', {}).get('response')})"
            for om in graph
        },
    )
    if output_path is not None:
        fig.savefig(output_path)
