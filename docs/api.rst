API
===

The API for FlexEval is still largely undocumented, although the package is not large.

A good place to start is with the Pydantic class :class:`~flexeval.schema.evalrun_schema.EvalRun`, which defines the inputs expected by FlexEval.

Data sources
------------

FlexEval accepts several kinds of data source, all sharing a common
:class:`~flexeval.schema.evalrun_schema.DataSource` base:

.. inheritance-diagram:: flexeval.schema.evalrun_schema.FileDataSource
                         flexeval.schema.evalrun_schema.NamedDataSource
                         flexeval.schema.evalrun_schema.IterableDataSource
   :parts: 1
   :top-classes: flexeval.schema.evalrun_schema.DataSource

Database models
---------------

Loaded data is stored in a hierarchy of `peewee <https://docs.peewee-orm.com/>`_
models, all descending from a common base:

.. inheritance-diagram:: flexeval.classes.dataset.Dataset
                         flexeval.classes.thread.Thread
                         flexeval.classes.turn.Turn
                         flexeval.classes.message.Message
                         flexeval.classes.tool_call.ToolCall
                         flexeval.classes.metric.Metric
                         flexeval.classes.eval_set_run.EvalSetRun
   :parts: 1
   :top-classes: flexeval.classes.base.BaseModel

Packages
--------

.. autosummary::
   :toctree: generated
   :recursive:

   flexeval
