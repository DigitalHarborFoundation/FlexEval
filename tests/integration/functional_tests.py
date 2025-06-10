"""Functional tests for FlexEval

We'll run simple evaluations and verify the database entries look as expected

Make sure your current directory is src/llm-evals
Then run
>  python -m unittest tests.functional_tests

"""

import os
import sqlite3
import unittest

import pandas as pd

from flexeval.runner import run


class TestSuite01(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_suite_01",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    @classmethod
    def tearDownClass(cls):
        # here, we'd delete the database?
        pass

    def test_tables_exist(self):
        table_names = [
            "dataset",
            "evalsetrun",
            "thread",
            "turn",
            "message",
            "toolcall",
            "metric",
        ]
        # write assertions here
        print(self.database_path)
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
                "select metric_value from metric where evalsetrun_id=1 and dataset_id=1 and thread_id=1 and turn_id=1 and evaluation_name = 'string_length'"
            ).fetchall()
        self.assertNotEqual(
            len(metric), 0, "No rows returned for string_length metric; should have 1."
        )
        self.assertEqual(
            len(metric), 1, "More than one row was returned for string_length metric."
        )
        self.assertAlmostEqual(metric[0][0], 12)

    def test_tables_have_right_rows(self):
        # this suite has one jsonl, simple.jsonl, which has 2 rows.
        # the first row has 3 turns. the second row also has 3 turns.
        helper_test_tables_have_right_rows(self, ((3, 3),))

    def test_string_length_has_function_label(self):
        with sqlite3.connect(self.database_path) as connection:
            result = connection.execute(
                """select evaluation_type from metric 
                where 1=1
                and evaluation_name = 'string_length'
                """
            ).fetchall()
            self.assertGreater(len(result), 0)
            self.assertTrue(all([i[0] == "function" for i in result]))


def helper_test_tables_have_right_rows(
    test_instance: unittest.TestCase, expected_num_turns: tuple
):
    """
    Check row counts on various tables:
    - evalsetrun should always have one row
    - dataset should have one row per jsonl file
    - thread should have one row for every row in every jsonl file
    - turn should have one row for every turn in every jsonl file
    expected_num_turns is a tuple that has
    - one entry per jsonl file, and
    - each of those entries is a tuple with
        - one entry per row in the corresponding jsonl file.
    The entry for each row is an int indicating the number of turns in that row.

    For example, for 1 dataset, 2 threads, and 8 turns in each, you should have
    expected_num_turns = ((4,4),)
    #the length of the tuple is the number of files or threads
    #

    """
    num_threads = len(expected_num_turns)
    expected_num_threads = [len(rows_in_file) for rows_in_file in expected_num_turns]
    table_and_row_counts = {
        "evalsetrun": 1,
        "dataset": num_threads,
        "thread": sum(expected_num_threads),
        "turn": sum([sum(turns_per_row) for turns_per_row in expected_num_turns]),
    }
    with sqlite3.connect(test_instance.database_path) as connection:
        for table in table_and_row_counts:
            data = pd.read_sql_query(f"select * from {table}", connection)
            # First, check that we have the right number of rows based on the dictionary above
            test_instance.assertEqual(
                data.shape[0],
                table_and_row_counts[table],
                f"Table {table} should have {table_and_row_counts[table]} rows but has {data.shape[0]} rows",
            )
            # Then do table-specific logic to make sure the evalsetrun_id, dataset_id, thread_id,
            # and turn_number ids are set up and have the right length
            if table == "thread":
                test_instance.assertEqual(
                    set(data["dataset_id"].value_counts().values),
                    set([len(turns_per_row) for turns_per_row in expected_num_turns]),
                    f"{table} table does not have correct counts for the dataset ids",
                )
            elif table == "turn":
                test_instance.assertEqual(
                    set(data["dataset_id"].value_counts().values),
                    set([sum(turns_per_row) for turns_per_row in expected_num_turns]),
                    f"{table} table does not have correct counts for the dataset ids",
                )


class TestSuite02(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_suite_02",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_simple_condition_is_met_once(self):
        # for the first dataset
        # the only readability score should be for the second entry
        with sqlite3.connect(self.database_path) as connection:
            metric = connection.execute(
                """select turn_id, metric_value from metric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and thread_id=1 --first row
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
                """select evalsetrun_id, dataset_id, thread_id, turn_id from metric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and thread_id=1 --first row
                and evaluation_name = 'string_length'
                and metric_value >= 15
                """
            ).fetchall()
            self.assertGreater(len(long_enough_strings), 0)
            # STEP 2
            # for every row in this, there should ALSO be a single entry for reading ease
            for row in long_enough_strings:
                with self.subTest():
                    reading_ease = connection.execute(
                        f"""select evalsetrun_id, dataset_id, thread_id, turn_id from metric 
                        where 1=1
                        and evalsetrun_id={row[0]}
                        and dataset_id={row[1]} --first file
                        and thread_id={row[2]} --first row
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
                """select evalsetrun_id, dataset_id, thread_id, turn_id from metric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and thread_id=1 --first row
                and evaluation_name = 'string_length'
                and metric_value < 15
                """
            ).fetchall()
            self.assertGreater(len(long_enough_strings), 0)
            # STEP 2
            # for every row in this, there should be ZERO rows that measure
            for row in long_enough_strings:
                with self.subTest():
                    reading_ease = connection.execute(
                        f"""select evalsetrun_id, dataset_id, thread_id, turn_id from metric 
                        where 1=1
                        and evalsetrun_id={row[0]}
                        and dataset_id={row[1]} --first file
                        and thread_id={row[2]} --first row
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
                    evalsetrun_id, dataset_id, thread_id, turn_id
                FROM 
                    metric t1
                WHERE 
                    evaluation_name = 'string_length' AND metric_value >= 15
                AND NOT EXISTS 
                    (
                    SELECT 1
                    FROM metric t2
                    WHERE t2.evalsetrun_id = t1.evalsetrun_id 
                        AND t2.dataset_id = t1.dataset_id
                        AND t2.thread_id = t1.thread_id
                        AND t2.turn_id = t1.turn_id
                        AND t2.evaluation_name = 'flesch_reading_ease'
                    ); 
                """
            ).fetchall()
        self.assertEqual(
            len(long_string_no_readingease),
            0,
            "For some rows with string length >= 15, no flesch_reading_ease score is reported",
        )

    def test_type_contradiction(self):
        # test: everything that has evaluation_type=function has null for EVERY column that starts with 'rubric'
        with sqlite3.connect(self.database_path) as connection:
            function_type = connection.execute(
                """
                SELECT 
                    evaluation_type, rubric_prompt, rubric_completion, rubric_model, rubric_completion_tokens, rubric_score
                FROM 
                    metric
                WHERE 
                    evaluation_type = 'function' 
                    AND 
                        (
                           rubric_prompt IS NOT NULL
                        OR rubric_completion IS NOT NULL
                        OR rubric_model IS NOT NULL
                        OR rubric_completion_tokens IS NOT NULL
                        OR rubric_score IS NOT NULL
                        )
                """
            ).fetchall()

        self.assertEqual(
            len(function_type),
            0,
            "Contradiction: function type rows with rubric-associated values",
        )


class TestSuite03(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_suite_03",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_tables_have_right_rows(self):
        # this suite has two jsonls, simple.jsonl and multiturn.jsonl,
        # simple.json  has 2 rows.
        # the first row has 3 turns. the second row also has 3 turns.
        # multiturn.jsonl has 3 rows.
        # the first row has 3 turns, the second row has 3 turns, and the third row has four turns
        helper_test_tables_have_right_rows(self, ((3, 3), (3, 3, 4)))

    def test_one_row_per_metric_without_dependency(self):
        # test for function_metric with no dependency,
        # every (jsonl/row/turn/metric) combo should get just one row in Metrics
        with sqlite3.connect(self.database_path) as connection:
            duplicated_metric = connection.execute(
                """
                SELECT 
                    evalsetrun_id, dataset_id, thread_id, turn_id, evaluation_name, metric_name, COUNT(*) as count 
                FROM 
                    metric 
                GROUP BY 
                    evalsetrun_id, dataset_id, thread_id, turn_id, evaluation_name, metric_name
                HAVING
                    COUNT(*) > 1
                """
            ).fetchall()
        self.assertEqual(len(duplicated_metric), 0, "Duplicated rows!")


class TestSuite04(unittest.TestCase):
    # rubric associated tests
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests
        # in this case, we'd run the evals here using subprocess or something, or maybe main.py
        run(
            eval_name="test_suite_04",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
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
                    metric 
                WHERE 1=1
                    AND evaluation_type = 'rubric'
                """
            ).fetchall()
        expected_values = [0.0, 1.0]
        for row in rubric_metric:
            with self.subTest():
                self.assertIn(
                    row[1],
                    expected_values,
                    f"Output value is not expected for row {row[0]}",
                )

    def test_rubric_not_null(self):
        # test: every row with evaluation_type=rubric should not contain null for rubric-related columns
        with sqlite3.connect(self.database_path) as connection:
            function_type = connection.execute(
                """
                SELECT 
                    evaluation_type, rubric_prompt, rubric_completion, rubric_model, rubric_completion_tokens, rubric_score
                FROM 
                    metric
                WHERE 
                    evaluation_type = 'rubric' 
                    AND 
                        (
                           rubric_prompt IS NULL
                        OR rubric_completion IS NULL
                        OR rubric_model IS NULL
                        OR rubric_completion_tokens IS NULL
                        OR rubric_score IS NULL
                        )
                """
            ).fetchall()

        self.assertEqual(
            len(function_type), 0, "Null values found in rows where type = rubric"
        )

    # %%

    def test_rubric_dependency(self):
        # test: For EVERY turn where the role is user, \
        # the same turn ALSO has a is_student_acting_as_actor entry
        with sqlite3.connect(self.database_path) as connection:
            user_no_tutor_acting_check = connection.execute(
                """
                SELECT 
                    evalsetrun_id, dataset_id, thread_id, turn_id
                FROM 
                    metric t1
                WHERE 
                    evaluation_name = 'is_role' 
                    AND metric_name = 'user'
                    AND metric_value = 1.0
                AND NOT EXISTS 
                    (
                    SELECT 1
                    FROM metric t2
                    WHERE t2.evalsetrun_id = t1.evalsetrun_id 
                        AND t2.dataset_id = t1.dataset_id
                        AND t2.thread_id = t1.thread_id
                        AND t2.turn_id = t1.turn_id
                        AND t2.evaluation_name = 'is_student_acting_as_tutor'
                    ); 
                """
            ).fetchall()
        self.assertEqual(
            len(user_no_tutor_acting_check),
            0,
            "For some rows where the role is user, no is_student_acting_as_tutor is reported",
        )


class TestSuite01_langgraph(unittest.TestCase):
    """TODO - can we just somehow combine this with the other?"""

    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_suite_01_langgraph",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    @classmethod
    def tearDownClass(cls):
        # here, we'd delete the database?
        pass

    def test_tables_exist(self):
        table_names = [
            "dataset",
            "evalsetrun",
            "thread",
            "turn",
            "message",
            "toolcall",
            "metric",
        ]
        # write assertions here
        print(self.database_path)
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
                "select metric_value from metric where evalsetrun_id=1 and dataset_id=1 and thread_id=1 and turn_id=1 and evaluation_name = 'string_length'"
            ).fetchall()
        self.assertNotEqual(
            len(metric), 0, "No rows returned for string_length metric; should have 1."
        )
        self.assertEqual(
            len(metric), 1, "More than one row was returned for string_length metric."
        )
        self.assertAlmostEqual(metric[0][0], 22)  # len('factor 190,913,277,151')

    def test_tables_have_right_rows(self):
        # this suite has 2 conversations with 8 rows each, so 16 total turns
        helper_test_tables_have_right_rows(self, ((4, 4),))

    def test_string_length_has_function_label(self):
        with sqlite3.connect(self.database_path) as connection:
            result = connection.execute(
                """select evaluation_type from metric 
                where 1=1
                and evaluation_name = 'string_length'
                """
            ).fetchall()
            self.assertGreater(len(result), 0)
            self.assertTrue(all([i[0] == "function" for i in result]))


class TestSuite02_langgraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_suite_02_langgraph",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_simple_condition_is_met_once(self):
        # for the first dataset
        # the only readability score should be for the second entry
        with sqlite3.connect(self.database_path) as connection:
            metric = connection.execute(
                """select turn_id, metric_value from metric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and thread_id=1 --first row
                and evaluation_name = 'flesch_reading_ease'
                """
            ).fetchall()
        self.assertEqual(
            len(metric), 2, "Expected 2 turns with long enough text to evaluate"
        )
        self.assertAlmostEqual(metric[0][0], 2)

    def test_simple_condition_is_always_met(self):
        # STEP 1 - find all cases where string_length >= 50
        # STEP 2 - every single one of those cases should also have a flesch_reading_ease entry for the same turn

        # STEP 1
        with sqlite3.connect(self.database_path) as connection:
            long_enough_strings = connection.execute(
                """select evalsetrun_id, dataset_id, thread_id, turn_id from metric 
                where 1=1
                and evalsetrun_id=1 
                and dataset_id=1 --first file
                and thread_id=1 --first row
                and evaluation_name = 'string_length'
                and metric_value >= 50
                """
            ).fetchall()
            self.assertGreater(len(long_enough_strings), 0)
            # STEP 2
            # for every row in this, there should ALSO be a single entry for reading ease
            for row in long_enough_strings:
                with self.subTest():
                    reading_ease = connection.execute(
                        f"""select evalsetrun_id, dataset_id, thread_id, turn_id from metric 
                        where 1=1
                        and evalsetrun_id={row[0]}
                        and dataset_id={row[1]} --first file
                        and thread_id={row[2]} --first row
                        and turn_id={row[3]}
                        and evaluation_name = 'flesch_reading_ease'
                        and metric_value IS NOT NULL
                        """
                    ).fetchall()
                    # there's exactly ONE row for each turn that has long enough string length
                    self.assertEqual(len(reading_ease), 1)

        # # now let's look at the converse
        # for every too-short string, there are zero rows
        with sqlite3.connect(self.database_path) as connection:
            too_short_strings = connection.execute(
                """select evalsetrun_id, dataset_id, thread_id, turn_id from metric
                where 1=1
                and evalsetrun_id=1
                and dataset_id=1 --first file
                and thread_id=1 --first row
                and evaluation_name = 'string_length'
                and metric_value < 50
                """
            ).fetchall()
            self.assertGreater(len(too_short_strings), 0)
            # STEP 2
            # for every row in this, there should be ZERO rows that measure
            for row in too_short_strings:
                with self.subTest():
                    reading_ease = connection.execute(
                        f"""select evalsetrun_id, dataset_id, thread_id, turn_id from metric
                        where 1=1
                        and evalsetrun_id={row[0]}
                        and dataset_id={row[1]} --first file
                        and thread_id={row[2]} --first row
                        and turn_id={row[3]}
                        and evaluation_name = 'flesch_reading_ease'
                        and metric_value IS NOT NULL
                        """
                    ).fetchall()
                    # there are ZERO rows for strings that are too short
                    self.assertEqual(len(reading_ease), 0)

    def test_multirow_dependency(self):
        # test for EVERY turn where the string_length is >= 50, \
        # the same turn ALSO has a flesch_reading_ease entry
        with sqlite3.connect(self.database_path) as connection:
            long_string_no_readingease = connection.execute(
                """
                SELECT 
                    evalsetrun_id, dataset_id, thread_id, turn_id
                FROM 
                    metric t1
                WHERE 
                    evaluation_name = 'string_length' AND metric_value >= 50
                AND NOT EXISTS 
                    (
                    SELECT 1
                    FROM metric t2
                    WHERE t2.evalsetrun_id = t1.evalsetrun_id 
                        AND t2.dataset_id = t1.dataset_id
                        AND t2.thread_id = t1.thread_id
                        AND t2.turn_id = t1.turn_id
                        AND t2.evaluation_name = 'flesch_reading_ease'
                    ); 
                """
            ).fetchall()
        self.assertEqual(
            len(long_string_no_readingease),
            0,
            "For some rows with string length >= 50, no flesch_reading_ease score is reported",
        )

    def test_type_contradiction(self):
        # test: everything that has evaluation_type=function has null for EVERY column that starts with 'rubric'
        with sqlite3.connect(self.database_path) as connection:
            function_type = connection.execute(
                """
                SELECT 
                    evaluation_type, rubric_prompt, rubric_completion, rubric_model, rubric_completion_tokens, rubric_score
                FROM 
                    metric
                WHERE 
                    evaluation_type = 'function' 
                    AND 
                        (
                           rubric_prompt IS NOT NULL
                        OR rubric_completion IS NOT NULL
                        OR rubric_model IS NOT NULL
                        OR rubric_completion_tokens IS NOT NULL
                        OR rubric_score IS NOT NULL
                        )
                """
            ).fetchall()

        self.assertEqual(
            len(function_type),
            0,
            "Contradiction: function type rows with rubric-associated values",
        )

    def test_count_function_calls(self):
        with sqlite3.connect(self.database_path) as connection:
            # connection.row_factory = sqlite3.Row
            function_calls = connection.execute(
                """
                SELECT 
                    *
                FROM 
                    metric
                WHERE 
                    evaluation_name = 'count_numeric_tool_call_params_by_name' 
                """
            ).fetchall()

        self.assertEqual(
            len(function_calls),
            2,
            "There should be one metric for each thread, and there are 2 threads",
        )


class TestSuite04_langgraph(unittest.TestCase):
    # rubric associated tests
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests
        # in this case, we'd run the evals here using subprocess or something, or maybe main.py
        run(
            eval_name="test_suite_04_langgraph",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_rubric_metric_value(self):
        # test if the rubric output expected values
        with sqlite3.connect(self.database_path) as connection:
            rubric_metric = connection.execute(
                """
                SELECT 
                    turn_id, metric_value 
                FROM 
                    metric 
                WHERE 1=1
                    AND evaluation_type = 'rubric'
                """
            ).fetchall()
        expected_values = [0.0, 1.0]
        for row in rubric_metric:
            with self.subTest():
                self.assertIn(
                    row[1],
                    expected_values,
                    f"Output value is not expected for row {row[0]}",
                )

    def test_rubric_not_null(self):
        # test: every row with evaluation_type=rubric should not contain null for rubric-related columns
        with sqlite3.connect(self.database_path) as connection:
            function_type = connection.execute(
                """
                SELECT
                    evaluation_type, rubric_prompt, rubric_completion, rubric_model, rubric_completion_tokens, rubric_score
                FROM
                    metric
                WHERE
                    evaluation_type = 'rubric'
                    AND
                        (
                           rubric_prompt IS NULL
                        OR rubric_completion IS NULL
                        OR rubric_model IS NULL
                        OR rubric_completion_tokens IS NULL
                        OR rubric_score IS NULL
                        )
                """
            ).fetchall()

        self.assertEqual(
            len(function_type), 0, "Null values found in rows where type = rubric"
        )

    def test_rubric_dependency(self):
        # test: For EVERY turn where the role is user, \
        # the same turn ALSO has a is_student_acting_as_actor entry
        with sqlite3.connect(self.database_path) as connection:
            user_no_tutor_acting_check = connection.execute(
                """
                SELECT
                    evalsetrun_id, dataset_id, thread_id, turn_id
                FROM
                    metric t1
                WHERE
                    evaluation_name = 'is_role'
                    AND metric_name = 'user'
                    AND metric_value = 1.0
                AND NOT EXISTS
                    (
                    SELECT 1
                    FROM metric t2
                    WHERE t2.evalsetrun_id = t1.evalsetrun_id
                        AND t2.dataset_id = t1.dataset_id
                        AND t2.thread_id = t1.thread_id
                        AND t2.turn_id = t1.turn_id
                        AND t2.evaluation_name = 'is_student_acting_as_tutor'
                    );
                """
            ).fetchall()
        self.assertEqual(
            len(user_no_tutor_acting_check),
            0,
            "For some rows where the role is user, no is_student_acting_as_tutor is reported",
        )


class FunctionMetricValidation(unittest.TestCase):
    def test_default_kwargs01(self):
        run(
            eval_name="test_default_kwargs_01",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )


class ConfigFailures(unittest.TestCase):
    @unittest.expectedFailure
    def test_config_failure_01(cls):
        run(
            eval_name="config_failure_01",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
        )

    @unittest.expectedFailure
    def test_config_failure_02(cls):
        run(
            eval_name="config_failure_02",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
        )

    @unittest.expectedFailure
    def test_config_failure_03(cls):
        run(
            eval_name="config_failure_03",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
        )

    @unittest.expectedFailure
    def test_config_failure_04(cls):
        run(
            eval_name="config_failure_04",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
        )

    @unittest.expectedFailure
    def test_config_failure_05(cls):
        run(
            eval_name="config_failure_05",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
        )

    @unittest.expectedFailure
    def test_config_failure_06(cls):
        run(
            eval_name="config_failure_06",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
        )

    @unittest.expectedFailure
    def test_config_failure_07(cls):
        run(
            eval_name="config_failure_07",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
        )


class TestBasicFunctionMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_basic_function_metrics_01",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_correct_metric_levels(self):
        # Expect to have one is_role evaluation for every Turn, at the
        # turn level, all with metric_name assistant, and two is_role
        # evaluations for every Message, one with metric_name assistant
        # and one with metric_name user.
        with sqlite3.connect(self.database_path) as connection:
            num_turns = connection.execute(
                """
                SELECT COUNT(*) FROM turn
                """
            ).fetchone()[0]

            turn_level_metrics = connection.execute(
                """
                SELECT 
                    dataset_id, turn_id, message_id
                FROM 
                    metric
                WHERE 1=1
                    AND metric_level = 'Turn'
                    AND evaluation_name = 'is_role'
                """
            ).fetchall()
            self.assertEqual(
                len(turn_level_metrics),
                num_turns,
                f"Expected one metric for each Turn for the is_role evaluation, but there were {num_turns} and {turn_level_metrics} metrics.",
            )
            represented_turns = set()
            for metric in turn_level_metrics:
                # Expect each turn to be represented exactly once.
                # No metric should have a message level set. All dataset_ids should be 1
                dataset_id, turn_id, message_id = metric
                self.assertEqual(dataset_id, 1, "Expected all dataset ids to be 1")
                self.assertFalse(
                    turn_id in represented_turns,
                    f"The turn id {turn_id} appeared more than once, but each turn should have one is_role only.",
                )
                represented_turns.add(turn_id)
                self.assertIsNone(
                    message_id,
                    f"No turn level metrics should also have a message id, but found message id {message_id}",
                )

            num_messages = connection.execute(
                """
                SELECT COUNT(*) FROM message
                """
            ).fetchone()[0]
            message_level_metrics = connection.execute(
                """
                SELECT 
                    dataset_id, turn_id, message_id, metric_name, metric_value
                FROM 
                    metric
                WHERE 1=1
                    AND metric_level = 'Message'
                    AND evaluation_name = 'is_role'
                """
            ).fetchall()
            self.assertEqual(
                len(message_level_metrics),
                num_messages * 2,
                (
                    f"Expected two metrics for each Message for the is_role "
                    f"evaluation, but there were {num_turns} and {turn_level_metrics} metrics."
                ),
            )
            represented_messages = {}
            for metric in message_level_metrics:
                # Expect each message to be represented twice, with opposite values for the two evals
                # No metric should have a message level set. All dataset_ids should be 1
                dataset_id, turn_id, message_id, metric_name, metric_value = metric
                self.assertEqual(dataset_id, 1, "Expected all dataset ids to be 1")
                self.assertIsNone(
                    turn_id,
                    f"No message level metrics should also have a turn id, but found message id {message_id}",
                )
                if message_id not in represented_messages:
                    represented_messages[message_id] = {}
                self.assertFalse(
                    metric_name in represented_messages[message_id],
                    (
                        f"The metric {metric_name} for is_role appeared more than once, "
                        "but each message should have of these metrics only."
                    ),
                )
                represented_messages[message_id][metric_name] = metric_value
                self.assertIn(
                    metric_name,
                    ["user", "assistant"],
                    f"Metric name should be user or assistant but was {metric_name}",
                )
                if len(represented_messages[message_id]) == 2:
                    self.assertNotEqual(
                        represented_messages[message_id]["user"],
                        represented_messages[message_id]["assistant"],
                        (
                            f"Message id {message_id} had the same value for is_role user and "
                            "  is_role assistant"
                        ),
                    )


class TestBasicFunctionMetrics_langgraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_basic_function_metrics_01_langgraph",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_correct_metric_levels(self):
        # Expect to have one is_role evaluation for every Turn, at the
        # turn level, all with metric_name assistant, and two is_role
        # evaluations for every Message, one with metric_name assistant
        # and one with metric_name user.
        with sqlite3.connect(self.database_path) as connection:
            num_turns = connection.execute(
                """
                SELECT COUNT(*) FROM turn
                """
            ).fetchone()[0]

            turn_level_metrics = connection.execute(
                """
                SELECT 
                    dataset_id, turn_id, message_id
                FROM 
                    metric
                WHERE 1=1
                    AND metric_level = 'Turn'
                    AND evaluation_name = 'is_role'
                """
            ).fetchall()
            self.assertEqual(
                len(turn_level_metrics),
                num_turns,
                f"Expected one metric for each Turn for the is_role evaluation, but there were {num_turns} and {turn_level_metrics} metrics.",
            )
            represented_turns = set()
            for metric in turn_level_metrics:
                # Expect each turn to be represented exactly once.
                # No metric should have a message level set. All dataset_ids should be 1
                dataset_id, turn_id, message_id = metric
                self.assertEqual(dataset_id, 1, "Expected all dataset ids to be 1")
                self.assertFalse(
                    turn_id in represented_turns,
                    f"The turn id {turn_id} appeared more than once, but each turn should have one is_role only.",
                )
                represented_turns.add(turn_id)
                self.assertIsNone(
                    message_id,
                    f"No turn level metrics should also have a message id, but found message id {message_id}",
                )

            num_messages = connection.execute(
                """
                SELECT COUNT(*) FROM message
                """
            ).fetchone()[0]
            message_level_metrics = connection.execute(
                """
                SELECT 
                    dataset_id, turn_id, message_id, metric_name, metric_value
                FROM 
                    metric
                WHERE 1=1
                    AND metric_level = 'Message'
                    AND evaluation_name = 'is_role'
                """
            ).fetchall()
            self.assertEqual(
                len(message_level_metrics),
                num_messages * 2,
                (
                    f"Expected two metrics for each Message for the is_role "
                    f"evaluation, but there were {num_turns} and {turn_level_metrics} metrics."
                ),
            )
            represented_messages = {}
            for metric in message_level_metrics:
                # Expect each message to be represented twice, with opposite values for the two evals
                # No metric should have a message level set. All dataset_ids should be 1
                dataset_id, turn_id, message_id, metric_name, metric_value = metric
                self.assertEqual(dataset_id, 1, "Expected all dataset ids to be 1")
                self.assertIsNone(
                    turn_id,
                    f"No message level metrics should also have a turn id, but found message id {message_id}",
                )
                if message_id not in represented_messages:
                    represented_messages[message_id] = {}
                self.assertFalse(
                    metric_name in represented_messages[message_id],
                    (
                        f"The metric {metric_name} for is_role appeared more than once, "
                        "but each message should have of these metrics only."
                    ),
                )
                represented_messages[message_id][metric_name] = metric_value
                self.assertIn(
                    metric_name,
                    ["user", "assistant"],
                    f"Metric name should be user or assistant but was {metric_name}",
                )
                if len(represented_messages[message_id]) == 2:
                    self.assertNotEqual(
                        represented_messages[message_id]["user"],
                        represented_messages[message_id]["assistant"],
                        (
                            f"Message id {message_id} had the same value for is_role user and "
                            "  is_role assistant"
                        ),
                    )


## TODO: TC - make LangGraph version
class TestListStringInputFunctionMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        # in this case, we run the evals via main.py
        run(
            eval_name="test_list_string_function_metrics",
            config_path="tests/integration/config-tests.yaml",
            evals_path="tests/integration/evals.yaml",
            clear_tables=True,
        )
        cls.database_path = os.environ["DATABASE_PATH"]

    def test_reading_ease_levels_by_level(self):
        message_id_to_reading_ease = {1: 119.19, 2: 119.19, 3: 35.61, 4: 77.91}
        message_id_to_reading_ease_context_only = {
            1: 206.84,
            2: 119.19,
            3: 119.19,
            4: 92.8,
        }
        turn_id_to_reading_ease = {1: 119.19, 2: 83.32, 3: 77.91}
        turn_id_to_reading_ease_context_only = {1: 206.84, 2: 119.19, 3: 92.8}
        with sqlite3.connect(self.database_path) as connection:
            reading_ease_metrics = connection.execute(
                """
                    SELECT 
                        turn_id, message_id, context_only, metric_level, metric_name, metric_value
                    FROM 
                        metric
                    WHERE 1=1
                        AND thread_id = 1
                        AND evaluation_name = 'flesch_reading_ease'
                    """
            ).fetchall()
            for result in reading_ease_metrics:
                (
                    turn_id,
                    message_id,
                    context_only,
                    metric_level,
                    metric_name,
                    metric_value,
                ) = result
                comparison_dict = None
                comparison_id = None
                if metric_level == "Message":
                    comparison_id = message_id
                    if context_only:
                        comparison_dict = message_id_to_reading_ease_context_only
                    else:
                        comparison_dict = message_id_to_reading_ease
                elif metric_level == "Turn":
                    comparison_id = turn_id
                    if context_only:
                        comparison_dict = turn_id_to_reading_ease_context_only
                    else:
                        comparison_dict = turn_id_to_reading_ease
                else:
                    raise Exception(
                        f"Expected only Message and Turn levels for reading ease but found {metric_level}"
                    )

                self.assertAlmostEqual(
                    comparison_dict[comparison_id],
                    metric_value,
                    msg="Metric value for reading ease not equal to expected value",
                )

    def test_count_messages_per_role(self):
        thread_and_turn_id_to_role_entries = {
            1: {1: {"user": 1}, 2: {"assistant": 2}, 3: {"user": 1}},
            2: {4: {"user": 1}, 5: {"assistant": 2}, 6: {"user": 1}},
            3: {
                7: {"user": 1},
                8: {"assistant": 2},
                9: {"user": 2},
                10: {"assistant": 1},
            },
        }
        thread_id_to_role_entries = {}
        for (
            thread_id,
            turn_to_role_entries,
        ) in thread_and_turn_id_to_role_entries.items():
            cur_role_entries = {}
            for turn, role_entries in turn_to_role_entries.items():
                for role, count in role_entries.items():
                    if role not in cur_role_entries:
                        cur_role_entries[role] = 0
                    cur_role_entries[role] += count
            thread_id_to_role_entries[thread_id] = cur_role_entries

        with sqlite3.connect(self.database_path) as connection:
            role_entry_metrics = connection.execute(
                """
                    SELECT 
                        thread_id, turn_id, metric_level, metric_name, metric_value
                    FROM 
                        metric
                    WHERE 1=1
                        AND thread_id = 1
                        AND evaluation_name = 'count_messages_per_role'
                    """
            ).fetchall()
            for result in role_entry_metrics:
                thread_id, turn_id, metric_level, metric_name, metric_value = result
                if metric_level == "Thread":
                    self.assertEqual(
                        thread_id_to_role_entries[thread_id][metric_name],
                        metric_value,
                        f"Wrong count for role {metric_name} in thread {thread_id}",
                    )
                elif metric_level == "Turn":
                    self.assertEqual(
                        thread_and_turn_id_to_role_entries[thread_id][turn_id][
                            metric_name
                        ],
                        metric_value,
                        f"Wrong count for role {metric_name} in turn {turn_id}",
                    )


# other tests

## basic - are the table rows being populated
# there shoulld be exactly one row in EvalSetRun
# every jsonl gets an entry in Dataset
# every (jsonl/row) get an entry in DatasetRow
# also, every (jsonl/row/turn) gets an entry in Turn
# for function_metric with no dependency, every (jsonl/row/turn/metric) combo gets a row in Metrics

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
