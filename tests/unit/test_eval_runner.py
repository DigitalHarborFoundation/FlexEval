import unittest

from flexeval.classes.eval_runner import EvalRunner
from flexeval.io.parsers import yaml_parser
from flexeval.schema import evalrun_schema
from tests.unit import mixins


class TestEvalRunner(mixins.DotenvMixin, unittest.TestCase):
    def test_build_eval_runner(self):
        config_path = "tests/resources/test_config.yaml"
        config = yaml_parser.load_config_from_yaml(config_path)
        evals_path = "tests/resources/test_evals.yaml"
        evals = yaml_parser.load_evals_from_yaml(evals_path)
        eval = evals["length_test"]

        data_sources = [evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")]
        database_path = ".unittest/unittest.db"
        evalrun = evalrun_schema.EvalRun(
            data_sources=data_sources,
            database_path=database_path,
            eval=eval,
            config=config,
        )

        runner = EvalRunner(evalrun)
        runner.shutdown_logging()
