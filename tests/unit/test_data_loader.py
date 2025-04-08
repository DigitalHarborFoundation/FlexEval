import pathlib
import tempfile
import unittest

from flexeval import data_loader
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_runner import EvalRunner


class TempPathMixin:
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = pathlib.Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()


class TestDataLoader(TempPathMixin, unittest.TestCase):
    def test_load_jsonl(self):
        config_path = "tests/resources/test_config.yaml"
        evals_path = "tests/resources/test_evals.yaml"
        runner = EvalRunner(
            eval_name="length_test",
            config_path=config_path,
            evals_path=evals_path,
            clear_tables=True,
        )
        # data_loader.load_jsonl(dataset, "tests/resources/test_dataset.jsonl")
