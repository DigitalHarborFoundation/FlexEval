import json
import unittest
from datetime import datetime
from typing import Annotated

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from flexeval import run_utils
from flexeval.classes.eval_runner import EvalRunner
from flexeval.io.parsers import yaml_parser
from flexeval.schema import evalrun_schema
from tests.unit import mixins


class TestDataLoader(mixins.DotenvMixin, unittest.TestCase):
    def test_load_jsonl(self):
        config_path = "tests/resources/test_config.yaml"
        config = yaml_parser.load_config_from_yaml(config_path)
        evals_path = "tests/resources/test_evals.yaml"
        evals = yaml_parser.load_evals_from_yaml(evals_path)
        eval = evals["length_test"]
        data_sources = [evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")]
        database_path = ".unittest/unittest.db"
        eval_run = evalrun_schema.EvalRun(
            data_sources=data_sources,
            database_path=database_path,
            eval=eval,
            config=config,
        )
        runner = EvalRunner(eval_run)

        eval_set_run = run_utils.build_eval_set_run(runner)
        datasets = run_utils.build_evalsetrun_datasets(eval_run, eval_set_run)
        self.assertGreater(len(datasets), 0)
        for dataset in datasets:
            self.assertTrue(dataset.is_loaded)
            self.assertGreater(len(list(dataset.threads)), 0)

    def test_load_jsonl_nosystem(self):
        data_sources = [
            evalrun_schema.FileDataSource(path="tests/data/simple.jsonl"),
            evalrun_schema.FileDataSource(path="tests/data/simple_nosystem.jsonl"),
        ]
        config_path = "tests/resources/test_config.yaml"
        config = yaml_parser.load_config_from_yaml(config_path)
        evals_path = "tests/resources/test_evals.yaml"
        evals = yaml_parser.load_evals_from_yaml(evals_path)
        eval = evals["length_test"]
        database_path = ".unittest/unittest.db"
        eval_run = evalrun_schema.EvalRun(
            data_sources=data_sources,
            database_path=database_path,
            eval=eval,
            config=config,
        )
        runner = EvalRunner(eval_run)

        eval_set_run = run_utils.build_eval_set_run(runner)
        datasets = run_utils.build_evalsetrun_datasets(eval_run, eval_set_run)
        self.assertEqual(len(datasets), 2)
        for dataset in datasets:
            self.assertTrue(dataset.is_loaded)

    def test_load_jsonl_metadata(self):
        """Tests the inclusion of metadata in JSONL files."""
        data_sources = [
            evalrun_schema.FileDataSource(path="tests/data/simple_metadata.jsonl"),
        ]
        config_path = "tests/resources/test_config.yaml"
        config = yaml_parser.load_config_from_yaml(config_path)
        evals_path = "tests/resources/test_evals.yaml"
        evals = yaml_parser.load_evals_from_yaml(evals_path)
        eval = evals["length_test"]
        database_path = ".unittest/unittest.db"
        eval_run = evalrun_schema.EvalRun(
            data_sources=data_sources,
            database_path=database_path,
            eval=eval,
            config=config,
        )
        runner = EvalRunner(eval_run)

        eval_set_run = run_utils.build_eval_set_run(runner)
        datasets = run_utils.build_evalsetrun_datasets(eval_run, eval_set_run)
        self.assertEqual(len(datasets), 1)

        dataset = datasets[0]
        for thread in dataset.threads:
            metadata = json.loads(thread.metadata)
            self.assertIn("key_1", metadata)
            self.assertEqual(metadata["key_1"], "value_1")
            self.assertIn("key_2", metadata)
            self.assertEqual(metadata["key_2"]["nested_key"], "nested_value")
            self.assertNotIn("input", metadata)
            for i, message in enumerate(thread.messages):
                metadata = json.loads(message.metadata)
                self.assertNotIn("role", metadata)
                self.assertIn("index", metadata)
                self.assertEqual(metadata["index"], i)
            break


class TestLoadDatasetsControlFlow(mixins.DotenvMixin, unittest.TestCase):
    """Tests for the control flow logic in run_utils.load_datasets()."""

    DB_PATH = ".unittest/test_control_flow.db"

    def _init_db(self, clear_tables=True):
        from flexeval import db_utils

        db_utils.initialize_database(self.DB_PATH, clear_tables=clear_tables)

    def _make_eval_run(self, data_sources, **config_kwargs):
        """Helper to build a minimal EvalRun with given data sources and config overrides."""
        return evalrun_schema.EvalRun(
            data_sources=data_sources,
            database_path=self.DB_PATH,
            eval=evalrun_schema.eval_schema.Eval(
                metrics=evalrun_schema.eval_schema.Metrics()
            ),
            config=evalrun_schema.config_schema.Config(**config_kwargs),
        )

    def test_named_datasource_success(self):
        """NamedDataSource finds an existing loaded dataset by name."""
        self._init_db(clear_tables=True)

        # First, create and load a dataset
        eval_run = self._make_eval_run(
            [
                evalrun_schema.FileDataSource(
                    path="tests/data/simple.jsonl", name="my_dataset"
                )
            ]
        )
        datasets = run_utils.load_datasets(eval_run)
        self.assertEqual(len(datasets), 1)
        self.assertTrue(datasets[0].is_loaded)

        # Now look it up via NamedDataSource
        eval_run2 = self._make_eval_run(
            [evalrun_schema.NamedDataSource(name="my_dataset")]
        )
        datasets2 = run_utils.load_datasets(eval_run2)
        self.assertEqual(len(datasets2), 1)
        self.assertEqual(datasets2[0].id, datasets[0].id)

    def test_named_datasource_not_found(self):
        """NamedDataSource raises ValueError when no matching dataset exists."""
        self._init_db(clear_tables=True)
        eval_run = self._make_eval_run(
            [evalrun_schema.NamedDataSource(name="nonexistent")]
        )
        with self.assertRaises(ValueError):
            run_utils.load_datasets(eval_run)

    def test_file_datasource_reuse_by_name(self):
        """A named FileDataSource is reused when reuse_dataset_by_name=True."""
        from flexeval.classes.dataset import Dataset

        self._init_db(clear_tables=True)
        eval_run = self._make_eval_run(
            [
                evalrun_schema.FileDataSource(
                    path="tests/data/simple.jsonl", name="reuse_me"
                )
            ],
            reuse_dataset_by_name=True,
        )
        datasets1 = run_utils.load_datasets(eval_run)
        self.assertEqual(len(datasets1), 1)

        # Second call — same name, should reuse
        eval_run2 = self._make_eval_run(
            [
                evalrun_schema.FileDataSource(
                    path="tests/data/simple.jsonl", name="reuse_me"
                )
            ],
            reuse_dataset_by_name=True,
        )
        datasets2 = run_utils.load_datasets(eval_run2)
        self.assertEqual(len(datasets2), 1)
        self.assertEqual(datasets2[0].id, datasets1[0].id)

        # Only one Dataset in DB
        all_datasets = list(Dataset.select())
        self.assertEqual(len(all_datasets), 1)

    def test_raise_on_duplicate_dataset_name(self):
        """Raises ValueError when duplicate name exists and raise_on_duplicate_dataset_name=True."""
        self._init_db(clear_tables=True)
        eval_run = self._make_eval_run(
            [
                evalrun_schema.FileDataSource(
                    path="tests/data/simple.jsonl", name="dup_name"
                )
            ],
            reuse_dataset_by_name=False,
            raise_on_duplicate_dataset_name=True,
        )
        run_utils.load_datasets(eval_run)

        # Second call with same name — should raise
        eval_run2 = self._make_eval_run(
            [
                evalrun_schema.FileDataSource(
                    path="tests/data/simple.jsonl", name="dup_name"
                )
            ],
            reuse_dataset_by_name=False,
            raise_on_duplicate_dataset_name=True,
        )
        with self.assertRaises(ValueError):
            run_utils.load_datasets(eval_run2)

    def test_raise_on_unnamed_dataset(self):
        """Raises ValueError when dataset is unnamed and raise_on_unnamed_dataset=True."""
        self._init_db(clear_tables=True)
        eval_run = self._make_eval_run(
            [evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")],
            raise_on_unnamed_dataset=True,
        )
        with self.assertRaises(ValueError):
            run_utils.load_datasets(eval_run)

    def test_datasource_type_mismatch_warning(self):
        """Logs a warning when reusing a dataset with a different datasource type."""
        self._init_db(clear_tables=True)

        # Create a dataset with IterableDataSource type
        eval_run = self._make_eval_run(
            [
                evalrun_schema.IterableDataSource(
                    name="type_mismatch",
                    contents=[
                        {
                            "input": [
                                {"role": "user", "content": "Hi"},
                                {"role": "assistant", "content": "Hello"},
                            ]
                        }
                    ],
                )
            ],
            reuse_dataset_by_name=True,
        )
        run_utils.load_datasets(eval_run)

        # Now try to reuse it with a FileDataSource of the same name
        eval_run2 = self._make_eval_run(
            [
                evalrun_schema.FileDataSource(
                    path="tests/data/simple.jsonl", name="type_mismatch"
                )
            ],
            reuse_dataset_by_name=True,
        )
        with self.assertLogs("flexeval.run_utils", level="WARNING") as cm:
            datasets = run_utils.load_datasets(eval_run2)
        self.assertEqual(len(datasets), 1)
        self.assertTrue(any("datasource type differs" in msg for msg in cm.output))


class TestIterableDataSourceReuse(mixins.DotenvMixin, unittest.TestCase):
    def test_unnamed_iterable_reused_across_runs(self):
        """An unnamed IterableDataSource shared across two EvalRuns should be
        auto-named and reused, not consumed twice."""
        import flexeval
        from flexeval.classes.dataset import Dataset
        from flexeval.metrics import access

        conversations = [
            {
                "input": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                ]
            },
        ]
        # Single unnamed IterableDataSource shared across both runs
        data_source = evalrun_schema.IterableDataSource(contents=conversations)
        data_sources = [data_source]

        eval_run_1 = evalrun_schema.EvalRun(
            data_sources=data_sources,
            database_path=".unittest/test_iterable_reuse.db",
            eval=evalrun_schema.eval_schema.Eval(
                metrics=evalrun_schema.eval_schema.Metrics(
                    function=[
                        evalrun_schema.eval_schema.FunctionItem(name="index_in_thread")
                    ]
                )
            ),
            config=evalrun_schema.config_schema.Config(clear_tables=True),
        )
        flexeval.run(eval_run_1)
        metrics_after_run_1 = access.get_all_metrics()
        self.assertGreater(len(metrics_after_run_1), 0, "Run 1 should produce metrics.")

        # Second run reuses the same data_source object (iterator already consumed)
        eval_run_2 = evalrun_schema.EvalRun(
            data_sources=data_sources,
            database_path=".unittest/test_iterable_reuse.db",
            eval=evalrun_schema.eval_schema.Eval(
                metrics=evalrun_schema.eval_schema.Metrics(
                    function=[
                        evalrun_schema.eval_schema.FunctionItem(name="index_in_thread")
                    ]
                )
            ),
            config=evalrun_schema.config_schema.Config(clear_tables=False),
        )
        flexeval.run(eval_run_2)
        metrics_after_run_2 = access.get_all_metrics()
        self.assertGreater(
            len(metrics_after_run_2),
            len(metrics_after_run_1),
            "Run 2 should produce additional metrics via dataset reuse.",
        )

        # Only one Dataset should exist (reused, not duplicated)
        all_datasets = list(Dataset.select())
        self.assertEqual(
            len(all_datasets), 1, "Expected one dataset (reused), not two."
        )
        self.assertTrue(all_datasets[0].name.startswith("_iterable_"))


class State(TypedDict):
    # TODO move this to some kind of langgraph utility file
    messages: Annotated[list, add_messages]


class TestLanggraphDataLoading(
    mixins.TempPathMixin, mixins.DotenvMixin, unittest.TestCase
):
    def test_load_langgraph(self):
        langgraph_db_path = self.temp_path / "data.db"

        def chatbot(state: State):
            return {"messages": [message for message in state["messages"]]}

        ## Build graph
        graph_builder = StateGraph(State)
        graph_builder.add_node("chatbot", chatbot)
        graph_builder.set_entry_point("chatbot")

        self.assertFalse(langgraph_db_path.exists())

        # Invoke graph - twice
        for i in range(2):
            with SqliteSaver.from_conn_string(str(langgraph_db_path)) as memory:
                graph = graph_builder.compile(checkpointer=memory)

                config = {"configurable": {"thread_id": datetime.now().isoformat()}}

                graph.invoke({"messages": ["factor 190,913,277,151"]}, config)
                graph.invoke(
                    {"messages": ["print them again but reverse the order"]}, config
                )
        self.assertTrue(langgraph_db_path.exists())

        # TODO finish implementing test
        # build an eval that points to langgraph_db_path
        # run the eval
        # verify that the expected data exists in the flexeval database
