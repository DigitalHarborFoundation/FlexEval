import unittest
import hashlib
import base64

from flexeval import compute_metrics, run_utils
from flexeval.schema import eval_schema, evalrun_schema, config_schema
from tests.unit import mixins
from flexeval.classes import eval_runner, eval_set_run


def build_evalsetrun(metrics: eval_schema.Metrics):
    data_sources = [evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")]
    # generate a database filename unique to this metric
    metrics_repr = (
        base64.urlsafe_b64encode(
            hashlib.sha256(metrics.model_dump_json().encode("utf-8")).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    database_path = f"tests/data/test_compute_metrics_{metrics_repr}.db"
    config = config_schema.Config(
        logs_path="tests/unit/logs/",
        clear_tables=True,
        raise_on_completion_error=True,
        raise_on_metric_error=True,
    )
    eval = eval_schema.Eval(
        metrics=metrics,
        grader_llm=eval_schema.GraderLlm(
            function_name="echo_completion", kwargs={"response": "YES"}
        ),
    )
    eval_run = evalrun_schema.EvalRun(
        data_sources=data_sources,
        database_path=database_path,
        eval=eval,
        config=config,
    )

    # build an EvalRunner and an EvalSetRun
    runner = eval_runner.EvalRunner(eval_run)
    assert (
        len(eval_set_run.EvalSetRun.select()) == 0
    ), "Unexpected state; didn't clear tables."
    evalsetrun = run_utils.build_eval_set_run(runner)

    # build datasets
    run_utils.build_datasets(runner, evalsetrun)
    for dataset in evalsetrun.datasets:
        dataset.load_data()

    return evalsetrun, runner


def get_constant_function(
    constant: int | float, metric_level: eval_schema.MetricLevel
) -> eval_schema.FunctionItem:
    return eval_schema.FunctionItem(
        name="constant", metric_level=metric_level, kwargs={"response": constant}
    )


def get_metrics() -> dict[str, eval_schema.Metrics]:
    metrics = eval_schema.Metrics(
        function=[
            eval_schema.FunctionItem(name="index_in_thread", metric_level="Message"),
            eval_schema.FunctionItem(
                name="identity",
                metric_level="Message",
                depends_on=[
                    eval_schema.DependsOnItem(
                        name="index_in_thread",
                        metric_max_value=0,
                        metric_level="Message",
                    )
                ],
            ),
            eval_schema.FunctionItem(name="index_in_thread", metric_level="Turn"),
            eval_schema.FunctionItem(name="identity", metric_level="ToolCall"),
            eval_schema.FunctionItem(name="tool_was_called", metric_level="Thread"),
        ],
        rubric=[],
    )
    f1 = get_constant_function(0, "Thread")
    f2 = get_constant_function(1, "Turn")
    f2.depends_on = [
        eval_schema.DependsOnItem(
            name="constant", type="function", kwargs={"response": 0}
        )
    ]
    f3 = get_constant_function(2, "Message")
    f3.depends_on = [
        eval_schema.DependsOnItem(
            name="constant", type="function", kwargs={"response": 1}
        )
    ]
    chain_metrics = eval_schema.Metrics(function=[f1, f2, f3])
    return {
        "one message function, no deps": eval_schema.Metrics(
            function=[
                eval_schema.FunctionItem(name="identity", metric_level="Message"),
            ],
        ),
        "simple_dep": metrics,
        "constant chain": chain_metrics,
    }


class TestMetricGraphBuilder(unittest.TestCase):
    def test_build_metric_structures(self):
        """Test build_metric_structures() returns reasonable results."""
        for metrics_descriptor, metrics in get_metrics().items():
            with self.subTest(metrics_descriptor=metrics_descriptor):
                evalsetrun, runner = build_evalsetrun(metrics)

                mgb = compute_metrics.MetricGraphBuilder()
                mgb.build_metric_structures(evalsetrun)
                self.assertGreater(len(mgb.metric_id_map), 0)
                self.assertGreater(len(mgb.metrics_by_level), 0)

    def test_build_thread_task_graph(self):
        all_metrics = get_metrics()
        for metrics_descriptor, metrics in all_metrics.items():
            with self.subTest(metrics_descriptor=metrics_descriptor):
                evalsetrun, runner = build_evalsetrun(metrics)
                mgb = compute_metrics.MetricGraphBuilder()
                mgb.build_metric_structures(evalsetrun)
                graphs = list(mgb.build_thread_task_graphs(evalsetrun))
                self.assertEqual(
                    len(graphs),
                    len(evalsetrun.threads),
                    "Expected one graph per thread.",
                )

                mc = runner.get_metric_computer()
                results = mc.process_thread_dependency_graphs(graphs)
                self.assertGreater(len(results), 0)

                if metrics_descriptor == "constant chain":
                    self.assertEqual(
                        len(results),
                        len(evalsetrun.threads)
                        + len(evalsetrun.turns)
                        + len(evalsetrun.messages),
                        "Expected one result for each thread, turn, and message.",
                    )
                    for result in results:
                        if result["metric_level"] == "Thread":
                            self.assertEqual(result["metric_value"], 0)
                        elif result["metric_level"] == "Turn":
                            self.assertEqual(result["metric_value"], 1)
                        elif result["metric_level"] == "Message":
                            self.assertEqual(result["metric_value"], 2)
