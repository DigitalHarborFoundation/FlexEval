# want to make sure the code works

# functionally, that means we want to run an evaluation on a KNOWN eval suite and an KNOWN dataset
# and we want the correct results to show up in the database

# that means that we need to write a test suite that uses an existing eval suite and dataset
# runs it, and then checks the database to make sure the output looks as expected

# we can vary this for different test suites, with different dependencies

# we should also create test suites that DO NOT work, and make sure they fail - this is called an "expected failure"

# what kinds of things would we check in the database?
# - if I run a function metric, results show up in the database for each input conversation
# - if there is a dependency, it's met
# - if I use kwargs, they get used and saved
# - if I try to use a function that doesn't exist, it fails but gives a useful error message


import unittest

from flexeval.runner import run


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
            eval_name="test01",
            config_filename="tests/integration/config-tests.yaml",
            evals_path="tests/tests.py",
        )
