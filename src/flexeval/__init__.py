"""FlexEval is a Python package for designing custom metrics, completion functions, and LLM-graded rubrics for evaluating the behavior of LLM-powered systems.

This top-level import exposes the :func:`~flexeval.runner.run` method."""

from flexeval import metrics
from flexeval.runner import run

__all__ = [
    "metrics",
    "run",
]
