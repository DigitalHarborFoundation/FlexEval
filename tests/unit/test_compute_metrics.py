import unittest

from flexeval import compute_metrics, run_utils
from flexeval.schema import eval_schema, evalrun_schema, config_schema
from tests.unit import mixins
from flexeval.classes import eval_runner


def build_evalsetrun(metrics: eval_schema.Metrics):
    data_sources = [evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")]
    database_path = "tests/data/unittest.db"
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
    evalsetrun = run_utils.build_eval_set_run(runner)

    # build datasets
    run_utils.build_datasets(runner, evalsetrun)
    for dataset in evalsetrun.datasets:
        dataset.load_data()

    return evalsetrun


class TestMetricGraphBuilder(unittest.TestCase):
    def test_build_metric_structures(self):
        metrics = eval_schema.Metrics(
            function=[
                eval_schema.FunctionItem(
                    name="index_in_thread", metric_level="Message"
                ),
                eval_schema.FunctionItem(name="index_in_thread", metric_level="Turn"),
                eval_schema.FunctionItem(name="identity", metric_level="ToolCall"),
                eval_schema.FunctionItem(name="tool_was_called", metric_level="Thread"),
            ],
            rubric=[],
        )
        evalsetrun = build_evalsetrun(metrics)

        mgb = compute_metrics.MetricGraphBuilder()
        mgb.build_metric_structures(evalsetrun)
        self.assertGreater(len(mgb.metric_id_map), 0)
        self.assertEqual(len(mgb.metrics_by_level), 4)
