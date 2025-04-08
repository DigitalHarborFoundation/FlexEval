import pathlib
import tempfile
import unittest

from flexeval import data_loader
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_runner import EvalRunner
from tests.unit import mixins


class TestDataLoader(mixins.DotenvMixin, unittest.TestCase):
    def test_load_jsonl(self):
        config_path = "tests/resources/test_config.yaml"
        evals_path = "tests/resources/test_evals.yaml"
        runner = EvalRunner(
            eval_name="length_test",
            config_path=config_path,
            evals_path=evals_path,
            clear_tables=True,
        )
        assert runner.eval is not None
