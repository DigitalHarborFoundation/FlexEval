.. FlexEval documentation master file, originally created by sphinx-quickstart on 2025 July 3 12:21:33.

FlexEval documentation
======================

.. image:: https://img.shields.io/pypi/v/python-flexeval
   :target: https://pypi.org/project/python-flexeval/
   :alt: PyPI

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.12729993.svg
   :target: https://doi.org/10.5281/zenodo.12729993
   :alt: Zenodo DOI

.. image:: https://img.shields.io/github/license/DigitalHarborFoundation/FlexEval
   :target: https://github.com/DigitalHarborFoundation/FlexEval/blob/main/LICENSE
   :alt: FlexEval license

.. image:: https://img.shields.io/badge/issue_tracking-github-blue.svg
   :target: https://github.com/DigitalHarborFoundation/FlexEval/issues
   :alt: Issue tracking on GitHub

.. raw:: html

   <br>

.. image:: /_static/flexeval_banner.svg
   :alt: FlexEval banner


FlexEval is a tool for designing custom metrics, completion functions, and LLM-graded rubrics for evaluating the behavior of LLM-powered systems.

Read about the motivation and design of FlexEval in our `paper <https://doi.org/10.5281/zenodo.12729993>`_ at *Educational Data Mining* 2024.

:doc:`Get started <getting_started>` with FlexEval, go deeper with the :ref:`user_guide`, or learn by example in the :doc:`vignettes`.


Basic Usage
-----------

:ref:`Install <installation>` using pip:

.. code-block:: bash

   pip install python-flexeval

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

Read more in :doc:`getting_started` and see additional usage examples in the :doc:`vignettes`.

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   
   getting_started
   user_guide/index
   vignettes
   api
