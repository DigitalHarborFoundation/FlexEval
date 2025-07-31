import base64
import hashlib
import re
import unittest
import unittest.mock

from flexeval import compute_metrics, run_utils
from flexeval.classes import eval_runner, eval_set_run
from flexeval.classes.message import Message
from flexeval.classes.metric import Metric
from flexeval.classes.turn import Turn
from flexeval.configuration import function_metrics
from flexeval.io.parsers import yaml_parser
from flexeval.metrics import save as save_metrics
from flexeval.schema import config_schema, eval_schema, evalrun_schema


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
    assert len(eval_set_run.EvalSetRun.select()) == 0, (
        "Unexpected state; didn't clear tables."
    )
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
    simple_dep_metrics = eval_schema.Metrics(
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
    second_turn_dep_metrics = eval_schema.Metrics(
        function=[
            eval_schema.FunctionItem(name="index_in_thread"),
            eval_schema.FunctionItem(
                name="constant",
                kwargs={"response": 57},
                depends_on=[
                    eval_schema.DependsOnItem(
                        name="index_in_thread",
                        metric_min_value=1,
                        metric_max_value=1,
                    )
                ],
            ),
        ]
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

    kwarg_dep = eval_schema.Metrics(
        function=[
            eval_schema.FunctionItem(name="is_role", kwargs={"role": "assistant"}),
            eval_schema.FunctionItem(
                name="flesch_reading_ease",
                depends_on=[
                    eval_schema.DependsOnItem(
                        name="is_role",
                        kwargs={"role": "assistant"},
                        metric_min_value=1,
                    )
                ],
            ),
        ]
    )
    return {
        "one message function, no deps": eval_schema.Metrics(
            function=[
                eval_schema.FunctionItem(name="identity", metric_level="Message"),
            ],
        ),
        "simple dep": simple_dep_metrics,
        "second turn dep": second_turn_dep_metrics,
        "constant chain": chain_metrics,
        "kwarg dep": kwarg_dep,
    }


class TestMetricGraphBuilder(unittest.TestCase):
    def test_build_metric_structures(self):
        """Test build_metric_structures() returns reasonable results."""
        for metrics_descriptor, metrics in get_metrics().items():
            with self.subTest(metrics_descriptor=metrics_descriptor):
                evalsetrun, _ = build_evalsetrun(metrics)

                mgb = compute_metrics.MetricGraphBuilder()
                mgb.build_metric_structures(evalsetrun)
                self.assertGreater(len(mgb.metric_id_map), 0)
                self.assertGreater(len(mgb.metrics_by_level), 0)

    def test_build_thread_task_graph(self):
        all_metrics = get_metrics()
        for metrics_descriptor, metrics in all_metrics.items():
            with self.subTest(metrics_descriptor=metrics_descriptor):
                evalsetrun, _ = build_evalsetrun(metrics)
                mgb = compute_metrics.MetricGraphBuilder()
                mgb.build_metric_structures(evalsetrun)
                graphs = list(mgb.build_thread_task_graphs(evalsetrun))
                self.assertEqual(
                    len(graphs),
                    len(evalsetrun.threads),
                    "Expected one graph per thread.",
                )


class TestMetricComputer(unittest.TestCase):
    def test_from_evalrun(self):
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

        # default case
        mc = compute_metrics.MetricComputer.from_evalrun(evalrun)
        self.assertEqual(len(mc.function_modules), 1)
        self.assertEqual(mc.function_modules[0], function_metrics)
        metric_function, _ = mc.find_function("count_emojis")
        test_object = unittest.mock.MagicMock(Message)
        test_object.get_content = unittest.mock.MagicMock(return_value="🌋")
        self.assertEqual(
            mc.invoke_function(metric_function, "Message", test_object, {}, False), 1
        )

        # non-existent module
        evalrun.function_modules = [
            "nonexistent_module",
        ]
        with self.assertRaises(ValueError):
            compute_metrics.MetricComputer.from_evalrun(evalrun)

        # built-in module
        evalrun.function_modules = ["re"]
        compute_metrics.MetricComputer.from_evalrun(evalrun)

        # built-in module, direct module reference
        evalrun.function_modules = [re]
        compute_metrics.MetricComputer.from_evalrun(evalrun)

        # module-style path
        evalrun.function_modules = ["tests.resources.function_metric"]
        mc = compute_metrics.MetricComputer.from_evalrun(evalrun)
        self.assertTrue(mc.function_modules[0].this_function_returns_true())

        # file path
        evalrun.function_modules = ["tests/resources/function_metric.py"]
        mc = compute_metrics.MetricComputer.from_evalrun(evalrun)
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

    def test_process_thread_dependency_graph(self):
        all_metrics = get_metrics()
        for metrics_descriptor, metrics in all_metrics.items():
            with self.subTest(metrics_descriptor=metrics_descriptor):
                evalsetrun, runner = build_evalsetrun(metrics)
                mgb = compute_metrics.MetricGraphBuilder()
                mgb.build_metric_structures(evalsetrun)
                graphs = list(mgb.build_thread_task_graphs(evalsetrun))

                # build metric computer and process dependency graphs
                mc = compute_metrics.MetricComputer.from_evalrun(runner.evalrun)
                results = []
                for graph in graphs:
                    results.extend(
                        mc.process_thread_dependency_graph(
                            graph, runner.evalrun.config.raise_on_metric_error
                        )
                    )
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

                if metrics_descriptor == "second turn dep":
                    save_metrics.save_metrics(results)
                    for turn in evalsetrun.turns:
                        if turn.index_in_thread != 1:
                            # non-second turns should not have a constant metric
                            self.assertEqual(len(turn.metrics_list), 1)
                            self.assertEqual(
                                turn.metrics_list.first().evaluation_name,
                                "index_in_thread",
                            )
                        else:
                            self.assertEqual(len(turn.metrics_list), 2)
                            constant_metric = list(turn.metrics_list)[-1]
                            self.assertEqual(
                                constant_metric.evaluation_name,
                                "constant",
                            )

                if metrics_descriptor == "kwarg dep":
                    save_metrics.save_metrics(results)
                    for turn in evalsetrun.turns:
                        is_role_assistant = (
                            turn.metrics_list.where(Metric.evaluation_name == "is_role")
                            .first()
                            .metric_value
                        )
                        if is_role_assistant == 1:
                            metric = turn.metrics_list.where(
                                Metric.evaluation_name == "flesch_reading_ease"
                            ).first()
                            self.assertIsNotNone(metric)
                            self.assertGreater(
                                metric.metric_value,
                                0,
                                "Expected positive flesch_reading_ease score.",
                            )
                        else:
                            self.assertEqual(
                                len(
                                    turn.metrics_list.where(
                                        Metric.evaluation_name == "flesch_reading_ease"
                                    )
                                ),
                                0,
                                "Should not compute flesch_reading_ease metric for non-assistant turns.",
                            )
                            self.assertEqual(
                                len(turn.metrics_list),
                                1,
                                "Only 1 metric expected for non-assistant turns.",
                            )

                    # select all "assistant" role Turns
                    # then validate that a reading ease score was also computed for that Turn
                    assistant_turns = (
                        Turn.select()
                        .join(Metric)
                        .where(Metric.evaluation_name == "is_role")
                        .where(Metric.metric_name == "assistant")
                        .where(Metric.metric_value == 1)
                    )
                    self.assertGreater(len(assistant_turns), 0)
                    for turn in assistant_turns:
                        metrics = turn.metrics_list
                        self.assertGreater(len(metrics), 1)

    def test_compute_metrics(self):
        all_metrics = get_metrics()
        for metrics_descriptor, metrics in all_metrics.items():
            with self.subTest(metrics_descriptor=metrics_descriptor):
                evalsetrun, runner = build_evalsetrun(metrics)
                compute_metrics.compute_metrics(runner.evalrun, evalsetrun)

    def test_compute_metrics_multiprocess(self):
        all_metrics = get_metrics()
        for metrics_descriptor, metrics in all_metrics.items():
            with self.subTest(metrics_descriptor=metrics_descriptor):
                evalsetrun, runner = build_evalsetrun(metrics)
                runner.evalrun.config.max_workers = 2
                compute_metrics.compute_metrics(runner.evalrun, evalsetrun)
