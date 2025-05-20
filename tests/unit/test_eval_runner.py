import pathlib
import tempfile
import unittest
import unittest.mock

from flexeval import data_loader
from flexeval.configuration import function_metrics
from flexeval.classes.dataset import Dataset
from flexeval.classes.eval_runner import EvalRunner
from tests.unit import mixins
from flexeval.classes.message import Message


class TestEvalRunner(mixins.DotenvMixin, unittest.TestCase):
    def test_build_eval_runner(self):
        config_path = "tests/resources/test_config.yaml"
        evals_path = "tests/resources/test_evals.yaml"
        runner = EvalRunner(
            eval_name="length_test",
            config_path=config_path,
            evals_path=evals_path,
            clear_tables=True,
        )
        assert runner.eval is not None
        runner.shutdown_logging()

    def test_get_metric_computer(self):
        config_path = "tests/resources/test_config.yaml"
        evals_path = "tests/resources/test_evals.yaml"
        runner = EvalRunner(
            eval_name="length_test",
            config_path=config_path,
            evals_path=evals_path,
            clear_tables=True,
        )
        # default case
        mc = runner.get_metric_computer()
        self.assertEqual(len(mc.function_modules), 1)
        self.assertEqual(mc.function_modules[0], function_metrics)
        metric_function, _ = mc.find_function("count_emojis")
        test_object = unittest.mock.MagicMock(Message)
        test_object.get_content = unittest.mock.MagicMock(return_value="🌋")
        self.assertEqual(mc.invoke_function(metric_function, test_object, {}, False), 1)

        # non-existent module
        runner.configuration["function_modules"] = [
            "nonexistent_module",
        ]
        with self.assertRaises(ValueError):
            runner.get_metric_computer()

        # built-in module
        runner.configuration["function_modules"] = ["re"]
        runner.get_metric_computer()

        # module-style path
        runner.configuration["function_modules"] = ["tests.resources.function_metric"]
        mc = runner.get_metric_computer()
        self.assertTrue(mc.function_modules[0].this_function_returns_true())

        # file path
        runner.configuration["function_modules"] = [
            "tests/resources/function_metric.py"
        ]
        mc = runner.get_metric_computer()
        self.assertTrue(mc.function_modules[0].this_function_returns_true())
        self.assertEqual(len(mc.function_modules), 2)
        self.assertEqual(mc.function_modules[1], function_metrics)

        metric_function, _ = mc.find_function("count_emojis")
        test_object = unittest.mock.MagicMock(Message)
        test_object.get_content = unittest.mock.MagicMock(return_value="🌋")
        self.assertEqual(
            mc.invoke_function(metric_function, test_object, {}, False), "overridden"
        )

        runner.shutdown_logging()
