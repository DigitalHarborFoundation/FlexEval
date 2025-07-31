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

Data Hierarchy
--------------

Metrics can operate at any of four levels of granularity:

- :class:`~flexeval.classes.thread.Thread`: Full conversation
- :class:`~flexeval.classes.turn.Turn`: Adjacent set of messages from the same user or assistant
- :class:`~flexeval.classes.message.Message`: Individual message from user or assistant
- :class:`~flexeval.classes.tool_call.ToolCall`: Function/tool invocation within a message

Metrics operate at the :class:`~flexeval.classes.turn.Turn` level by default, but you can override a :class:`~flexeval.schema.eval_schema.MetricItem`\'s ``metric_level``.
