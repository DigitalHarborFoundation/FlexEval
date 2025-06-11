import unittest

from flexeval.configuration import function_metrics
from flexeval import run_utils, log_utils
from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.message import Message
from flexeval.classes.turn import Turn
from flexeval.classes.thread import Thread
from flexeval.schema import EvalRun, FileDataSource, Config, Eval


def setUpModule():
    log_utils.set_up_logging()


class EvalSetRunTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run code that needs to run before ANY of the tests, and clear any existing data from tables
        data_sources = [FileDataSource(path="tests/data/simple.jsonl")]
        database_path = "tests/data/unit_function_metrics.db"
        config = Config(
            logs_path="tests/unit/logs/",
            clear_tables=True,
            raise_on_completion_error=True,
            raise_on_metric_error=True,
        )
        eval = Eval()
        eval_run = EvalRun(
            data_sources=data_sources,
            database_path=database_path,
            eval=eval,
            config=config,
        )

        # load datasets
        runner = EvalRunner(eval_run)
        evalsetrun = run_utils.build_eval_set_run(runner)
        run_utils.build_datasets(runner, evalsetrun)
        for dataset in evalsetrun.datasets:
            dataset.load_data()
        cls.evalsetrun = evalsetrun


class TestIndexInThread(EvalSetRunTestCase):
    def test_index_in_thread(self):
        threads = list(Thread.select())
        for thread in threads:
            turns = list(thread.turns.order_by(Turn.id))
            self.assertGreater(len(turns), 0, "Thread with no Turns.")
            for i, turn in enumerate(turns):
                self.assertEqual(i, function_metrics.index_in_thread(turn))
            messages = list(thread.messages.order_by(Message.id))
            self.assertGreater(len(messages), 0, "Thread with no Messages.")
            for i, message in enumerate(messages):
                self.assertEqual(i, function_metrics.index_in_thread(message))


class TestCountMessages(EvalSetRunTestCase):
    def test_count_messages(self):
        for thread in Thread.select():
            self.assertEqual(
                len(thread.messages), function_metrics.count_messages(thread)
            )
        for turn in Turn.select():
            self.assertEqual(len(turn.messages), function_metrics.count_messages(turn))
