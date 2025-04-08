import unittest

from flexeval import validate


class TestValidate(unittest.TestCase):
    def test_load(self):
        unittest.defaultTestLoader.loadTestsFromModule(validate)
