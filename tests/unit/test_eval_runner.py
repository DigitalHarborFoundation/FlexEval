import re
import unittest
import unittest.mock

from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.message import Message
from flexeval.configuration import function_metrics
from flexeval.io.parsers import yaml_parser
from tests.unit import mixins
from flexeval.schema import evalrun_schema


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

    def test_get_metric_computer(self):
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

        # default case
        mc = runner.get_metric_computer()
        self.assertEqual(len(mc.function_modules), 1)
        self.assertEqual(mc.function_modules[0], function_metrics)
        metric_function, _ = mc.find_function("count_emojis")
        test_object = unittest.mock.MagicMock(Message)
        test_object.get_content = unittest.mock.MagicMock(return_value="🌋")
        self.assertEqual(
            mc.invoke_function(metric_function, "Message", test_object, {}, False), 1
        )

        # non-existent module
        runner.evalrun.function_modules = [
            "nonexistent_module",
        ]
        with self.assertRaises(ValueError):
            runner.get_metric_computer()

        # built-in module
        runner.evalrun.function_modules = ["re"]
        runner.get_metric_computer()

        # built-in module, direct module reference
        runner.evalrun.function_modules = [re]
        runner.get_metric_computer()

        # module-style path
        runner.evalrun.function_modules = ["tests.resources.function_metric"]
        mc = runner.get_metric_computer()
        self.assertTrue(mc.function_modules[0].this_function_returns_true())

        # file path
        runner.evalrun.function_modules = ["tests/resources/function_metric.py"]
        mc = runner.get_metric_computer()
        self.assertTrue(mc.function_modules[0].this_function_returns_true())
        self.assertEqual(len(mc.function_modules), 2)
        self.assertEqual(mc.function_modules[1], function_metrics)

        metric_function, _ = mc.find_function("count_emojis")
        test_object = unittest.mock.MagicMock(Message)
        test_object.get_content = unittest.mock.MagicMock(return_value="🌋")
        self.assertEqual(
            mc.invoke_function(metric_function, "Message", test_object, {}, False),
            "overridden",
        )

        runner.shutdown_logging()
