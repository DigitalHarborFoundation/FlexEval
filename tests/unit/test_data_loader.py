import pathlib
import tempfile
import unittest

from flexeval import data_loader, run_utils
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_runner import EvalRunner
from tests.unit import mixins


class TempPathMixin:
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = pathlib.Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()


class TestDataLoader(TempPathMixin, mixins.DotenvMixin, unittest.TestCase):
    def test_load_jsonl(self):
        config_path = "tests/resources/test_config.yaml"
        evals_path = "tests/resources/test_evals.yaml"
        runner = EvalRunner(
            eval_name="length_test",
            config_path=config_path,
            evals_path=evals_path,
            clear_tables=True,
        )
        eval_set_run = run_utils.build_eval_set_run(runner)
        run_utils.build_datasets(runner, eval_set_run)
        for dataset in eval_set_run.datasets:
            dataset.load_data()


class TestLanggraphDataLoading(mixins.DotenvMixin, unittest.TestCase):
    def test_load_langgraph(self):
        data_filepath = "tests/data/simple.jsonl"
