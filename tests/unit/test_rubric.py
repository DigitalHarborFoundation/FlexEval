import unittest

from flexeval import rubric


class TestRubric(unittest.TestCase):
    def test_load_default_rubric_metrics(self):
        default_metrics = rubric.get_default_rubric_collection()
        self.assertGreater(len(default_metrics.rubrics), 0)
