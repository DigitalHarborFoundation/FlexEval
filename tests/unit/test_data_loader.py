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
