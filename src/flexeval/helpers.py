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


def _graph_node_label(om) -> str:
    """Build the display label for a single node in a metric dependency graph."""
    metric = om.metric
    return (
        f"{om.object.__class__.__name__} {om.object.id}\n"
        f"{metric.get('id')}("
        f"l={metric.get('metric_level')},"
        f"r={metric.get('kwargs', {}).get('response')})"
    )


def visualize_graph(graph: nx.DiGraph, ax=None, output_path: str | None = None):
    """Visualize graphs produced by :class:`~flexeval.compute_metrics.MetricGraphBuilder`.

    Args:
        graph (nx.DiGraph): The graph.
        ax (matplotlib.axes.Axes | None, optional): An existing Axes to draw into.
            If None, a new figure and axes are created.
        output_path (str | None, optional): If not None, save the figure using
            :meth:`matplotlib.pyplot.Figure.savefig`.

    Returns:
        tuple: The ``(fig, ax)`` the graph was drawn into.

    Raises:
        ImportError: If matplotlib is not installed.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for visualize_graph but is not installed. "
            "Install it with: pip install 'python-flexeval[viz]'"
        ) from e
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(12, 5))
    else:
        fig = ax.figure
    pos = nx.spring_layout(graph)
    nx.draw(graph, ax=ax, pos=pos)
    nx.draw_networkx_labels(
        graph,
        font_size=8,
        ax=ax,
        pos=pos,
        labels={om: _graph_node_label(om) for om in graph},
    )
    if output_path is not None:
        fig.savefig(output_path)
    return fig, ax
