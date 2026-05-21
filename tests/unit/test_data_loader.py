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
from flexeval.classes.dataset import Dataset
from flexeval.classes.thread import Thread
from flexeval.classes.message import Message
from flexeval.classes.eval_set_run import EvalSetRun, EvalSetRunDatasets

from flexeval.io.parsers import yaml_parser
from flexeval.schema import evalrun_schema
from tests.unit import mixins
from flexeval import db_utils
from flexeval.data_loader import load_langgraph_sqlite
import flexeval
from flexeval.metrics import access

from flexeval.classes.turn import Turn


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

    def test_stale_unloaded_dataset_is_cleaned_up(self):
        """An is_loaded=False Dataset (remnant of a crashed load) is dropped with a warning,
        its partial child rows are deleted, and the caller proceeds to create a fresh one.
        """
        self._init_db(clear_tables=True)

        # Simulate a crashed prior load: Dataset row committed but is_loaded still False,
        # with partial Thread and Message rows underneath it.
        stale = Dataset.create(
            datasource_type="FileDataSource", name="stale", is_loaded=False
        )
        Thread.create(dataset=stale, jsonl_thread_id=0)
        Message.create(
            dataset=stale,
            thread=stale.threads[0],
            index_in_thread=0,
            role="user",
            content="partial",
            context="[]",
            is_flexeval_completion=False,
        )

        with self.assertLogs("flexeval.run_utils", level="WARNING") as cm:
            result = run_utils.find_dataset_by_name("stale")
        self.assertIsNone(result)
        self.assertTrue(any("Dropping unloaded dataset" in m for m in cm.output))
        self.assertTrue(any("'threads': 1" in m for m in cm.output))
        self.assertTrue(any("'messages': 1" in m for m in cm.output))

        # Stale dataset and its children should be gone.
        self.assertEqual(Dataset.select().where(Dataset.name == "stale").count(), 0)
        self.assertEqual(Thread.select().count(), 0)
        self.assertEqual(Message.select().count(), 0)

        # A subsequent load_datasets call with the same name should succeed cleanly.
        eval_run = self._make_eval_run(
            [
                evalrun_schema.FileDataSource(
                    path="tests/data/simple.jsonl", name="stale"
                )
            ]
        )
        datasets = run_utils.load_datasets(eval_run)
        self.assertEqual(len(datasets), 1)
        self.assertTrue(datasets[0].is_loaded)

    def test_stale_unloaded_dataset_with_evalsetrun_link_raises(self):
        """If an is_loaded=False Dataset has derived rows (EvalSetRunDatasets or Metric),
        refuse to clean up — that's a real integrity violation, not a crashed load."""

        self._init_db(clear_tables=True)

        stale = Dataset.create(
            datasource_type="FileDataSource", name="stale_with_link", is_loaded=False
        )
        # Rogue derived row — shouldn't exist for is_loaded=False under the normal flow.
        esr = EvalSetRun.create(
            metrics="{}", metrics_graph_ordered_list="[]", do_completion=False
        )
        EvalSetRunDatasets.create(evalsetrun=esr, dataset=stale)

        with self.assertRaisesRegex(ValueError, "refusing to clean up"):
            run_utils.find_dataset_by_name("stale_with_link")


class TestIterableDataSourceReuse(mixins.DotenvMixin, unittest.TestCase):
    def test_unnamed_iterable_reused_across_runs(self):
        """An unnamed IterableDataSource shared across two EvalRuns should be
        auto-named and reused, not consumed twice."""
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


class TestJSONLDuplication(mixins.DotenvMixin, unittest.TestCase):
    """Tests for nb_evaluations_per_thread duplication in JSONL loading."""

    DB_PATH = ".unittest/test_jsonl_duplication.db"

    def _init_db(self, clear_tables=True):
        db_utils.initialize_database(self.DB_PATH, clear_tables=clear_tables)

    def test_load_jsonl_with_duplication(self):
        """Verify nb_evaluations_per_thread creates distinct duplicates with unique eval_run_thread_id."""
        self._init_db(clear_tables=True)

        # Create eval run with duplication
        eval_run = evalrun_schema.EvalRun(
            data_sources=[
                evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")
            ],
            database_path=self.DB_PATH,
            eval=evalrun_schema.eval_schema.Eval(
                metrics=evalrun_schema.eval_schema.Metrics()
            ),
            config=evalrun_schema.config_schema.Config(
                nb_evaluations_per_thread=3,
                max_n_conversation_threads=2,  # Select only 2 threads
            ),
        )
        datasets = run_utils.load_datasets(eval_run)
        self.assertEqual(len(datasets), 1)
        dataset = datasets[0]

        # Should create 2 threads * 3 duplicates = 6 total threads
        threads = list(Thread.select().where(Thread.dataset == dataset))
        self.assertEqual(len(threads), 6)

        # Group threads by jsonl_thread_id
        threads_by_jsonl_id = {}
        for thread in threads:
            jsonl_id = thread.jsonl_thread_id
            if jsonl_id not in threads_by_jsonl_id:
                threads_by_jsonl_id[jsonl_id] = []
            threads_by_jsonl_id[jsonl_id].append(thread)

        # Each jsonl_thread_id should have 3 duplicates
        self.assertEqual(len(threads_by_jsonl_id), 2)
        for jsonl_id, thread_list in threads_by_jsonl_id.items():
            self.assertEqual(len(thread_list), 3)

            # Check eval_run_thread_id pattern
            eval_run_ids = sorted([t.eval_run_thread_id for t in thread_list])
            expected_ids = [f"{jsonl_id}_0", f"{jsonl_id}_1", f"{jsonl_id}_2"]
            self.assertEqual(eval_run_ids, expected_ids)

            # Verify messages are identical across duplicates
            message_counts = [len(list(t.messages)) for t in thread_list]
            self.assertEqual(len(set(message_counts)), 1)  # All same count

    def test_load_jsonl_single_evaluation(self):
        """Verify default nb_evaluations_per_thread=1 creates single thread with eval_run_thread_id."""
        self._init_db(clear_tables=True)

        eval_run = evalrun_schema.EvalRun(
            data_sources=[
                evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")
            ],
            database_path=self.DB_PATH,
            eval=evalrun_schema.eval_schema.Eval(
                metrics=evalrun_schema.eval_schema.Metrics()
            ),
            config=evalrun_schema.config_schema.Config(
                nb_evaluations_per_thread=1, max_n_conversation_threads=1
            ),
        )
        datasets = run_utils.load_datasets(eval_run)
        dataset = datasets[0]

        threads = list(Thread.select().where(Thread.dataset == dataset))
        self.assertEqual(len(threads), 1)

        # Should have eval_run_thread_id even with single evaluation
        thread = threads[0]
        self.assertIsNotNone(thread.eval_run_thread_id)
        self.assertEqual(thread.eval_run_thread_id, f"{thread.jsonl_thread_id}_0")

    def test_load_iterable_no_eval_run_id(self):
        """Verify load_iterable doesn't set eval_run_thread_id (backward compatibility)."""
        self._init_db(clear_tables=True)

        conversations = [
            {
                "input": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                ]
            },
        ]
        eval_run = evalrun_schema.EvalRun(
            data_sources=[evalrun_schema.IterableDataSource(contents=conversations)],
            database_path=self.DB_PATH,
            eval=evalrun_schema.eval_schema.Eval(
                metrics=evalrun_schema.eval_schema.Metrics()
            ),
            config=evalrun_schema.config_schema.Config(),
        )
        datasets = run_utils.load_datasets(eval_run)
        dataset = datasets[0]

        threads = list(Thread.select().where(Thread.dataset == dataset))
        self.assertEqual(len(threads), 1)

        # eval_run_thread_id should be NULL for iterable
        thread = threads[0]
        self.assertIsNone(thread.eval_run_thread_id)

    def test_eval_run_thread_id_uniqueness(self):
        """Verify all eval_run_thread_id values are unique within a dataset."""
        self._init_db(clear_tables=True)

        eval_run = evalrun_schema.EvalRun(
            data_sources=[
                evalrun_schema.FileDataSource(path="tests/data/simple.jsonl")
            ],
            database_path=self.DB_PATH,
            eval=evalrun_schema.eval_schema.Eval(
                metrics=evalrun_schema.eval_schema.Metrics()
            ),
            config=evalrun_schema.config_schema.Config(
                nb_evaluations_per_thread=3,
            ),
        )
        datasets = run_utils.load_datasets(eval_run)
        dataset = datasets[0]

        threads = list(Thread.select().where(Thread.dataset == dataset))
        eval_run_ids = [t.eval_run_thread_id for t in threads]

        # All eval_run_thread_id values should be unique
        self.assertEqual(len(eval_run_ids), len(set(eval_run_ids)))

        # All should follow the pattern {jsonl_thread_id}_{index}
        for thread in threads:
            self.assertIsNotNone(thread.eval_run_thread_id)
            self.assertTrue("_" in thread.eval_run_thread_id)
            jsonl_id, index = thread.eval_run_thread_id.rsplit("_", 1)
            self.assertEqual(jsonl_id, thread.jsonl_thread_id)
            self.assertTrue(index.isdigit())


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

        # Load the LangGraph data into FlexEval
        db_path = str(self.temp_path / "flexeval.db")
        db_utils.initialize_database(db_path, clear_tables=True)
        ds = Dataset.create(
            name="test_lg",
            source=str(langgraph_db_path),
            datasource_type="langgraph_sqlite",
        )
        load_langgraph_sqlite(ds, str(langgraph_db_path))

        # 2 threads (one per graph.invoke loop iteration)
        threads = list(Thread.select().where(Thread.dataset == ds))
        self.assertEqual(len(threads), 2)

        # Each thread should have messages: the chatbot echoes back,
        # so 2 invokes per thread = 4 human messages + 4 echo messages
        for thread in threads:
            messages = list(
                Message.select()
                .where(Message.thread == thread)
                .order_by(Message.index_in_thread)
            )
            self.assertGreater(len(messages), 0)
            # First message should be from user
            self.assertEqual(messages[0].role, "user")
            self.assertEqual(messages[0].content, "factor 190,913,277,151")

        # Turns should have been created
        turns = list(Turn.select().where(Turn.dataset == ds))
        self.assertGreater(len(turns), 0)

    def test_load_langgraph_with_duplication(self):
        """Verify LangGraph duplication still works correctly after JSONL changes."""
        langgraph_db_path = self.temp_path / "data_dup.db"

        def chatbot(state: State):
            return {"messages": [message for message in state["messages"]]}

        ## Build graph
        graph_builder = StateGraph(State)
        graph_builder.add_node("chatbot", chatbot)
        graph_builder.set_entry_point("chatbot")

        # Create one thread
        with SqliteSaver.from_conn_string(str(langgraph_db_path)) as memory:
            graph = graph_builder.compile(checkpointer=memory)
            config = {"configurable": {"thread_id": "test_thread_1"}}
            graph.invoke({"messages": ["Hello"]}, config)

        # Load with duplication
        db_path = str(self.temp_path / "flexeval_dup.db")
        db_utils.initialize_database(db_path, clear_tables=True)
        ds = Dataset.create(
            name="test_lg_dup",
            source=str(langgraph_db_path),
            datasource_type="langgraph_sqlite",
        )
        load_langgraph_sqlite(ds, str(langgraph_db_path), nb_evaluations_per_thread=3)

        # Should create 3 duplicates of the thread
        threads = list(Thread.select().where(Thread.dataset == ds))
        self.assertEqual(len(threads), 3)

        # Check eval_run_thread_id pattern
        eval_run_ids = sorted([t.eval_run_thread_id for t in threads])
        expected_ids = ["test_thread_1_0", "test_thread_1_1", "test_thread_1_2"]
        self.assertEqual(eval_run_ids, expected_ids)

        # All should have same langgraph_thread_id
        lg_thread_ids = [t.langgraph_thread_id for t in threads]
        self.assertEqual(len(set(lg_thread_ids)), 1)
        self.assertEqual(lg_thread_ids[0], "test_thread_1")
