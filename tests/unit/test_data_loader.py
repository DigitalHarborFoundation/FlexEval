import unittest

from flexeval import data_loader


class TestDataLoader(unittest.TestCase):

    def test_load_jsonl(self):
        data_loader.load_jsonl()
