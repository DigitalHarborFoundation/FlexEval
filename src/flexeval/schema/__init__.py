"""Pydantic schema for the core configuration options used for FlexEval.

The top-level schema object is :class:`~flexeval.schema.evalrun_schema.EvalRun`.

See :mod:`~flexeval.classes` for the internal Peewee objects produced from the Pydantic configuration.
"""

from .config_schema import *
from .eval_schema import *
from .evalrun_schema import *
from .rubric_schema import *
