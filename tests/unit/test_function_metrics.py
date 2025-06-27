import unittest

from flexeval import log_utils
from flexeval.classes.message import Message
from flexeval.classes.thread import Thread
from flexeval.classes.turn import Turn
from flexeval.configuration import function_metrics
from tests.unit import mixins


def setUpModule():
    log_utils.set_up_logging()


class TestIndexInThread(mixins.DatasetsMixin, unittest.TestCase):
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


class TestCountMessages(mixins.DatasetsMixin, unittest.TestCase):
    def test_count_messages(self):
        for thread in Thread.select():
            self.assertEqual(
                len(thread.messages), function_metrics.count_messages(thread)
            )
        for turn in Turn.select():
            self.assertEqual(len(turn.messages), function_metrics.count_messages(turn))
