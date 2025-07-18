.. _getting_started:

Getting started
===============

.. _installation:

Installation
------------

FlexEval is available on `PyPI <https://www.pypi.org/project/python-flexeval/>`__ as ``python-flexeval``.

Install using `pip <https://pypi.org/project/python-flexeval>`__:

.. code-block:: bash

    pip install python-flexeval

Install using `poetry <https://python-poetry.org/>`__:

.. code-block:: bash

    poetry add python-flexeval

Install using `uv <https://docs.astral.sh/uv/>`__:

.. code-block:: bash

    uv add python-flexeval

.. _getting-started-usage:

Usage
-----

Create and run an evaluation:

.. code-block:: python

   import flexeval
   from flexeval.schema import Eval, EvalRun, FileDataSource, Metrics, FunctionItem, Config

   data_sources = [FileDataSource(path="vignettes/conversations.jsonl")]
   eval = Eval(metrics=Metrics(function=[FunctionItem(name="flesch_reading_ease")]))
   config = Config(clear_tables=True)
   eval_run = EvalRun(
       data_sources=data_sources,
       database_path="eval_results.db",
       eval=eval,
       config=config,
   )
   flexeval.run(eval_run)

This example computes `Flesch reading ease <https://en.wikipedia.org/wiki/Flesch%E2%80%93Kincaid_readability_tests#Flesch_reading_ease>`_ for every turn in a list of conversations provided in JSONL format. The metric values are stored in an SQLite database called ``eval_results.db``.

The basic approach:
 - Create an :class:`~flexeval.schema.eval_schema.Eval` defining the functions and metrics that should be computed on the inputs.
 - Create an :class:`~flexeval.schema.evalrun_schema.EvalRun` defining the input and output data sources.
 - Invoke :func:`~flexeval.runner.run` to execute the evaluation.

For more information about using FlexEval, continue on to the :ref:`user_guide`.

For usage examples, consult the :ref:`vignettes`.
