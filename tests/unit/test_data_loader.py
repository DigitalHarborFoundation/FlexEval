import json
import unittest
from datetime import datetime
from typing import Annotated

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from flexeval import run_utils, data_loader
from flexeval.classes.eval_runner import EvalRunner
from flexeval.classes.eval_set_run import EvalSetRun
from flexeval.classes.dataset import Dataset
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
        run_utils.build_datasets(runner, eval_set_run)
        for dataset in eval_set_run.datasets:
            dataset.load_data()

    def test_load_jsonl_nosystem(self):
        datasets = [
            "tests/data/simple.jsonl",
            "tests/data/simple_nosystem.jsonl",
        ]
        evalsetrun = EvalSetRun.create(
            dataset_files=json.dumps(datasets),
            metrics="",
            metrics_graph_ordered_list="",
            do_completion=False,
        )
        for dataset_filepath in evalsetrun.get_datasets():
            dataset = Dataset.create(
                evalsetrun=evalsetrun,
                filename=dataset_filepath,
            )
            dataset.load_data()
            # This is redundant, but just in case:
            data_loader.load_jsonl(dataset=dataset, filename=dataset_filepath)

    def test_load_jsonl_metadata(self):
        """Tests the inclusion of metadata in JSONL files."""
        datasets = [
            "tests/data/simple_metadata.jsonl",
        ]
        evalsetrun = EvalSetRun.create(
            dataset_files=json.dumps(datasets),
            metrics="",
            metrics_graph_ordered_list="",
            do_completion=False,
        )
        for dataset_filepath in evalsetrun.get_datasets():
            dataset = Dataset.create(
                evalsetrun=evalsetrun,
                filename=dataset_filepath,
            )
            dataset.load_data()
            # This is redundant, but just in case:
            data_loader.load_jsonl(dataset=dataset, filename=dataset_filepath)

            for thread in dataset.threads:
                metadata = json.loads(thread.metadata)
                assert "key_1" in metadata and metadata["key_1"] == "value_1"
                assert (
                    "key_2" in metadata
                    and metadata["key_2"]["nested_key"] == "nested_value"
                )
                assert "input" not in metadata
                for i, message in enumerate(thread.messages):
                    metadata = json.loads(message.metadata)
                    assert metadata["index"] == i
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
