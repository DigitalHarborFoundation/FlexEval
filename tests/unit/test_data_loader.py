import unittest

from flexeval.classes.Dataset import Dataset
from flexeval import data_loader


class TestDataLoader(unittest.TestCase):

    def test_load_jsonl(self):
        dataset = Dataset()
        data_loader.load_jsonl(dataset, "tests/resources/test_dataset.jsonl")
