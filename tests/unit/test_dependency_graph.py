import unittest

from flexeval import dependency_graph
from flexeval.schema import eval_schema


class TestDependencyGraph(unittest.TestCase):
    def test_create_metrics_graph(self):
        functions = []
        rubrics = []
        metrics = eval_schema.Metrics(function=functions, rubric=rubrics)
        graph = dependency_graph.create_metrics_graph(metrics)
        self.assertEqual(len(graph), 0)

        a = eval_schema.FunctionItem(name="a")
        b = eval_schema.FunctionItem(
            name="b", depends_on=[eval_schema.DependsOnItem(name="a")]
        )
        c = eval_schema.FunctionItem(
            name="c", depends_on=[eval_schema.DependsOnItem(name="b")]
        )
        functions = [a, b, c]
        graph = dependency_graph.create_metrics_graph(
            eval_schema.Metrics(function=functions, rubric=[])
        )
