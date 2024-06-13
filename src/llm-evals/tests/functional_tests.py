"""Functional tests for FlexEval

We'll run simple evaluations and verify the database entries look as expected

Make sure your current directory is src/llm-evals
Then run 
>  python -m unittest tests.functional_tests

"""

import unittest

import os
import sys
import sqlite3
import pandas

from main import run


class TestSuite01(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests
        # in this case, we'd run the evals here using subprocess or something, or maybe main.py
        run(
            eval_name="test_suite_01",
            config_path="config-tests.yaml",
            evals_path="tests/evals.yaml",
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    @classmethod
    def tearDownClass(cls):
        # here, we'd delete the database?
        # TODO delete database after use
        pass

    def test_tables_exist(self):
        # write assertions here
        table_names = ["dataset", "datasetrow", "evalsetrun", "turn", "turnmetric"]
        with sqlite3.connect(self.database_path) as connection:
            tables_in_database = connection.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
            tables_in_database = [i[0] for i in tables_in_database]
        for table_name in table_names:
            with self.subTest():
                self.assertIn(
                    table_name, tables_in_database, "Table is missing from database!"
                )

        # make sure there are no extra tables
        self.assertEqual(set(table_names), set(tables_in_database))

    def test_string_length_entry(self):
        # write assertions here
        with sqlite3.connect(self.database_path) as connection:
            metric = connection.execute(
                "select metric_value from turnmetric where evalsetrun_id=1 and dataset_id=1 and datasetrow_id=1 and turn_id=1 and evaluation_name = 'string_length'"
            ).fetchall()
        self.assertEqual(len(metric), 1, "More than one row was returned!")
        self.assertAlmostEqual(metric[0][0], 12)

    def test_abc(self):
        # write assertions here
        pass


class TestSuite02(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests
        # in this case, we'd run the evals here using subprocess or something, or maybe main.py
        run(
            eval_name="test_suite_02",
            config_path="config-tests.yaml",
            evals_path="tests/evals.yaml",
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_tables_exist(self):
        # for the first dataset
        # the only readability score should be for the second entry
        with sqlite3.connect(self.database_path) as connection:
            metric = connection.execute(
                """select turn_id, metric_value from turnmetric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and datasetrow_id=1 --first row
                and evaluation_name = 'flesch_reading_ease'
                """
            ).fetchall()
        self.assertEqual(len(metric), 1, "More than one row was returned!")
        self.assertAlmostEqual(metric[0][0], 2)


# other tests

## basic - are the table rows being populated
# there shoulld be exactly one row in EvalSetRun
# every jsonl gets an entry in Dataset
# every (jsonl/row) get an entry in DatasetRow
# also, every (jsonl/row/turn) gets an entry in Turn
# for function_metric with no dependency, every (jsonl/row/turn/metric) combo gets a row in TurnMetrics

# for 'multiturn', there should be 3 turns for the evaluation and not 4

# make sure all evaluation_name=string_length also have evaluation_type="function"

# everything that has evaluation_type=function has null for EVERY column that starts with 'rubric'

# some tests associated with rubrics...
