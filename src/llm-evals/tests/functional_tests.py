"""Functional tests for FlexEval

We'll run simple evaluations and verify the database entries look as expected

Make sure your current directory is src/llm-evals
Then run 
>  python -m unittest tests.functional_tests

"""

import unittest

import os
import sys

from main import run


class FunctionalTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests
        # in this case, we'd run the evals here using subprocess or something, or maybe main.py
        pass

    @classmethod
    def tearDownClass(cls):
        # here, we'd delete the database?
        pass

    def test_abc(self):
        # write assertions here
        run(
            eval_name="test_suite_01",
            config_path="config-tests.yaml",
            evals_path="tests/evals.yaml",
        )
