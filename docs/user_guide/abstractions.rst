.. _abstractions:

Abstractions
============

FlexEval's :ref:`API <api>` uses several abstractions. 
These abstractions are expressed through :mod:`pydantic` objects, and understanding them will enable you to have a nicer time using FlexEval.

Key abstractions
----------------

FlexEval is a tool for executing *evaluations*.

An evaluation is represented by :class:`flexeval.schema.eval_schema.Eval`, and contains a set of :class:`~flexeval.schema.eval_schema.MetricItem`\s to apply to the test data.

- **Functions**: :class:`~flexeval.schema.eval_schema.FunctionItem`\s apply a Python function to the test data, returning a numeric value.
- **Rubrics**: :class:`~flexeval.schema.eval_schema.RubricItem`\s use a configured :class:`~flexeval.schema.eval_schema.GraderLlm` function and the provided rubric template to generate a numeric score from an LLM's output.

You execute an :class:`~flexeval.schema.eval_schema.Eval` by creating an :class:`flexeval.schema.evalrun_schema.EvalRun`.
EvalRun contains:

- Data sources (conversations as inputs, an SQLite filepath as output)
- An :class:`~flexeval.schema.eval_schema.Eval` specification, containing the metrics to compute
- Sources for the metrics defined in the :class:`~flexeval.schema.eval_schema.Eval` e.g. Python modules containing the functions referenced in :class:`~flexeval.schema.eval_schema.FunctionItem`\s or YAML files containing the rubric templates.
- A :class:`~flexeval.schema.config_schema.Config` specification, describing how evaluation should be executed.

The :class:`~flexeval.schema.config_schema.Config` includes details about multi-threaded metric computation, about logging, etc.

Data Sources
------------

Data sources can be any of these types:

- :class:`~flexeval.schema.evalrun_schema.FileDataSource` (``type: file``): Load from a JSONL or LangGraph SQLite file. This is the most common data source.
- :class:`~flexeval.schema.evalrun_schema.NamedDataSource` (``type: named``): Reference a previously loaded dataset by name, enabling dataset reuse across eval runs.
- :class:`~flexeval.schema.evalrun_schema.IterableDataSource` (``type: iterable``): Load from an in-memory Python iterable (programmatic use only).

In YAML configurations, specify the ``type`` field::

    data_sources:
      - type: file
        path: conversations.jsonl

In Python, the type is set automatically when you construct the appropriate class::

    data_sources = [FileDataSource(path="conversations.jsonl")]

Data Hierarchy
--------------

Data is organized at several levels of granularity:

- :class:`~flexeval.classes.dataset.Dataset`: A loaded collection of conversations. Datasets can be shared across multiple eval runs.
- :class:`~flexeval.classes.thread.Thread`: Full conversation
- :class:`~flexeval.classes.turn.Turn`: Adjacent set of messages from the same user or assistant
- :class:`~flexeval.classes.message.Message`: Individual message from user or assistant
- :class:`~flexeval.classes.tool_call.ToolCall`: Function/tool invocation within a message

Metrics operate at the :class:`~flexeval.classes.turn.Turn` level by default, but you can override a :class:`~flexeval.schema.eval_schema.MetricItem`\'s ``metric_level``.
