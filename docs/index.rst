.. FlexEval documentation master file, created by
   sphinx-quickstart on Thu Jul  3 12:21:33 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

FlexEval documentation
======================

.. image:: /_static/flexeval_banner.svg
   :alt: FlexEval banner

|

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.12729993.svg
   :target: https://doi.org/10.5281/zenodo.12729993
   :alt: Zenodo

.. image:: https://img.shields.io/github/license/DigitalHarborFoundation/FlexEval
   :target: https://github.com/DigitalHarborFoundation/FlexEval/blob/main/LICENSE
   :alt: FlexEval license

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   
   vignettes
   api

.. .. include:: ../README.md
..   :parser: myst_parser.sphinx_

FlexEval is a tool for designing custom metrics, completion functions, and LLM-graded rubrics for evaluating the behavior of LLM-powered systems.

Additional details about FlexEval can be found in our `paper <EDM_2024_FlexEval.pdf>`_ at the *Educational Data Mining* 2024 conference.

Usage
=====

Basic usage:

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

See additional usage examples in the :doc:`vignettes`.