import unittest

from flexeval import rubric


class TestRubric(unittest.TestCase):

    def test_load_default_rubric_metrics(self):
        default_metrics = rubric.load_default_rubric_metrics()
        self.assertGreater(len(default_metrics), 0)
