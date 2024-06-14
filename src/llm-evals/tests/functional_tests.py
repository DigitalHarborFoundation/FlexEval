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
import pandas as pd

sys.path.append("../")
sys.path.append("../../")

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

    def test_tables_have_right_rows(self):
        #this suite has one jsonl, simple.jsonl, which has 2 rows.
        #the first row has 3 turns. the second row also has 3 turns.
        helper_test_tables_have_right_rows(self, ((3,3),))
    
    def test_abc(self):
        # write assertions here
        pass

def helper_test_tables_have_right_rows(test_instance: unittest.TestCase, 
                                       expected_num_turns: tuple):
    '''
    Check row counts on various tables:
    - evalsetrun should always have one row
    - dataset should have one row per jsonl file
    - datasetrow should have one row for every row in every jsonl file
    - turn show have one row for every turn in every jsonl file
    expected_num_turns is a tuple that has one entry per jsonl file, and each of those
    entries is a tuple with one entry per row in the corresponding jsonl file. The entry
    for each row is an int indicating the number of turns in that row.
    '''
    num_jsonl_files = len(expected_num_turns)
    expected_num_rows = [len(rows_in_file) for rows_in_file in expected_num_turns]
    table_and_row_counts = {
        'evalsetrun': 1, 
        'dataset': num_jsonl_files, 
        'datasetrow': sum(expected_num_rows), 
        'turn': sum([sum(turns_per_row) for turns_per_row in expected_num_turns])}  
    with sqlite3.connect(test_instance.database_path) as connection:
        for table in table_and_row_counts:
            data = pd.read_sql_query(f"select * from {table}", connection)
            # First, check that we have the right number of rows based on the dictionary above
            test_instance.assertEqual(data.shape[0], table_and_row_counts[table], 
                                      f"Table {table} should have {table_and_row_counts[table]} rows but has {data.shape[0]} rows")
            # Then do table-specific logic to make sure the evalsetrun_id, dataset_id, datasetrow_id, 
            # and turn_number ids are set up and have the right length  
            if table == 'datasetrow':
                test_instance.assertEqual(set(data["dataset_id"].value_counts().values),
                                          set([len(turns_per_row) for turns_per_row in expected_num_turns]),
                                          f"{table} table does not have correct counts for the dataset ids")
            elif table == 'turn':
                test_instance.assertEqual(set(data["dataset_id"].value_counts().values),
                                          set([sum(turns_per_row) for turns_per_row in expected_num_turns]),
                                          f"{table} table does not have correct counts for the dataset ids")

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

    def test_simple_condition_is_met_once(self):
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

    def test_simple_condition_is_always_met(self):
        # STEP 1 - find all cases where string_length >= 15
        # STEP 2 - every single one of those cases should also have a flesch_reading_ease entry for the same turn

        # STEP 1
        with sqlite3.connect(self.database_path) as connection:
            long_enough_strings = connection.execute(
                """select evalsetrun_id, dataset_id, datasetrow_id, turn_id from turnmetric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and datasetrow_id=1 --first row
                and evaluation_name = 'string_length'
                and metric_value >= 15
                """
            ).fetchall()
            # STEP 2
            # for every row in this, there should ALSO be a single entry for reading ease
            for row in long_enough_strings:
                with self.subTest():
                    reading_ease = connection.execute(
                        f"""select evalsetrun_id, dataset_id, datasetrow_id, turn_id from turnmetric 
                        where 1=1
                        and evalsetrun_id={row[0]}
                        and dataset_id={row[1]} --first file
                        and datasetrow_id={row[2]} --first row
                        and turn_id={row[3]}
                        and evaluation_name = 'flesch_reading_ease'
                        and metric_value IS NOT NULL
                        """
                    ).fetchall()
                    # there's exactly ONE row for each turn that has long enough string length
                    self.assertEqual(len(reading_ease), 1)

        # now let's look at the converse
        with sqlite3.connect(self.database_path) as connection:
            long_enough_strings = connection.execute(
                """select evalsetrun_id, dataset_id, datasetrow_id, turn_id from turnmetric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and datasetrow_id=1 --first row
                and evaluation_name = 'string_length'
                and metric_value < 15
                """
            ).fetchall()
            # STEP 2
            # for every row in this, there should be ZERO rows that measure
            for row in long_enough_strings:
                with self.subTest():
                    reading_ease = connection.execute(
                        f"""select evalsetrun_id, dataset_id, datasetrow_id, turn_id from turnmetric 
                        where 1=1
                        and evalsetrun_id={row[0]}
                        and dataset_id={row[1]} --first file
                        and datasetrow_id={row[2]} --first row
                        and turn_id={row[3]}
                        and evaluation_name = 'flesch_reading_ease'
                        and metric_value IS NOT NULL
                        """
                    ).fetchall()
                    # there's exactly ONE row for each turn that has long enough string length
                    self.assertEqual(len(reading_ease), 0)
                    
    def test_multirow_dependency(self):
        # test for EVERY turn where the string_length is >= 15, \
        # the same turn ALSO has a flesch_reading_ease entry
        with sqlite3.connect(self.database_path) as connection:
            long_string_no_readingease = connection.execute(
                """
                SELECT 
                    evalsetrun_id, dataset_id, datasetrow_id, turn_id
                FROM 
                    turnmetric t1
                WHERE 
                    evaluation_name = 'string_length' AND metric_value >= 15
                AND NOT EXISTS 
                    (
                    SELECT 1
                    FROM turnmetric t2
                    WHERE t2.evalsetrun_id = t1.evalsetrun_id 
                        AND t2.dataset_id = t1.dataset_id
                        AND t2.datasetrow_id = t1.datasetrow_id
                        AND t2.turn_id = t1.turn_id
                        AND t2.evaluation_name = 'flesch_reading_ease'
                    ); 
                """         
            ).fetchall()
        self.assertEqual(len(long_string_no_readingease), 0, "For some rows with string length >= 15, no flesch_reading_ease score is reported")
    
    def test_type_contradiction(self):
        # test: everything that has evaluation_type=function has null for EVERY column that starts with 'rubric'
        with sqlite3.connect(self.database_path) as connection:
            function_type = connection.execute(
                """
                SELECT 
                    evaluation_type, rubric_prompt, rubric_completion, rubric_model, rubric_completion_tokens, rubric_score
                FROM 
                    turnmetric
                WHERE 
                    evaluation_type = 'function' 
                    AND rubric_prompt IS NOT NULL
                    AND rubric_completion IS NOT NULL
                    AND rubric_model IS NOT NULL
                    AND rubric_completion_tokens IS NOT NULL
                    AND rubric_score IS NOT NULL
                """         
            ).fetchall()
        self.assertEqual(len(function_type), 0, "Contradiction: function type rows with rubric-associated values")
            
## some tests associated with rubrics...
# if type is rubric, all the rubric_related columns should not be null

# the type of the value should match the expectations
 


class TestSuite03(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests
        # in this case, we'd run the evals here using subprocess or something, or maybe main.py
        run(
            eval_name="test_suite_03",
            config_path="config-tests.yaml",
            evals_path="tests/evals.yaml",
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_tables_have_right_rows(self):
        #this suite has two jsonls, simple.jsonl and multiturn.jsonl, 
        # simple.json  has 2 rows.
        #the first row has 3 turns. the second row also has 3 turns.
        # multiturn.jsonl has 3 rows.
        # the first row has 3 turns, the second row has 3 turns, and the third row has four turns
        helper_test_tables_have_right_rows(self, ((3,3),(3, 3, 4)))

    def test_one_row_per_metric_without_dependency(self):
        # test for function_metric with no dependency, 
        # every (jsonl/row/turn/metric) combo should get just one row in TurnMetrics
        with sqlite3.connect(self.database_path) as connection:
            duplicated_metric = connection.execute(
                """
                SELECT 
                    evalsetrun_id, dataset_id, datasetrow_id, turn_id, evaluation_name, COUNT(*) as count 
                FROM 
                    turnmetric 
                GROUP BY 
                    evalsetrun_id, dataset_id, datasetrow_id, turn_id, evaluation_name
                HAVING
                    COUNT(*) > 1
                """
            ).fetchall()
        self.assertEqual(len(duplicated_metric), 0, "Duplicated rows!") 

# other tests

class TestSuite04(unittest.TestCase):
    # rubric associated tests 
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests
        # in this case, we'd run the evals here using subprocess or something, or maybe main.py
        run(
            eval_name="test_suite_04",
            config_path="config-tests.yaml",
            evals_path="tests/evals.yaml",
        )
        cls.database_path = os.environ["DATABASE_PATH"]
        
    def test_rubric_metric_value(self):
        # test if the rurbric output expected values 
        with sqlite3.connect(self.database_path) as connection:
            rubric_metric = connection.execute(
                """
                SELECT 
                    turn_id, metric_value 
                FROM 
                    turnmetric 
                WHERE 1=1
                    AND evaluation_type = 'rubric'
                """
            ).fetchall()
        expected_values = [0.0, 1.0]
        for row in rubric_metric:
            with self.subTest():
                self.assertIn(row[1], expected_values, f"Output value is not expected for row {row[0]}")







## basic - are the table rows being populated
# there shoulld be exactly one row in EvalSetRun
# every jsonl gets an entry in Dataset
# every (jsonl/row) get an entry in DatasetRow
# also, every (jsonl/row/turn) gets an entry in Turn
# for function_metric with no dependency, every (jsonl/row/turn/metric) combo gets a row in TurnMetrics

# for EVERY turn where the string_length is >= 15, the same turn ALSO has a flesch_reading_ease entry

# for 'multiturn', there should be 3 turns for the evaluation and not 4

# make sure all evaluation_name=string_length also have evaluation_type="function"

# everything that has evaluation_type=function has null for EVERY column that starts with 'rubric'

# some tests associated with rubrics...


# def suite():
#     suite = unittest.TestSuite()
#     # Add test classes in the desired order
#     suite.addTest(unittest.makeSuite(TestSuite01))
#     suite.addTest(unittest.makeSuite(TestSuite02))
#     return suite

# if __name__ == "__main__":
#     runner = unittest.TextTestRunner()
#     runner.run(suite())