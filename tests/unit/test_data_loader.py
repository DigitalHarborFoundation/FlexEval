import unittest
from datetime import datetime
from typing import Annotated

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from flexeval import run_utils
from flexeval.io.parsers import yaml_parser
from flexeval.classes.eval_runner import EvalRunner
from tests.unit import mixins


class TestDataLoader(mixins.DotenvMixin, unittest.TestCase):
    def test_load_jsonl(self):
        config_path = "tests/resources/test_config.yaml"
        config = yaml_parser.load_config_from_yaml(config_path)
        evals_path = "tests/resources/test_evals.yaml"
        evals = yaml_parser.load_evals_from_yaml(evals_path)
        eval = evals["length_test"]
        runner = EvalRunner(eval, config)

        eval_set_run = run_utils.build_eval_set_run(runner)
        run_utils.build_datasets(runner, eval_set_run)
        for dataset in eval_set_run.datasets:
            dataset.load_data()


class State(TypedDict):
    # TODO move this to some kind of langgraph utility file
    messages: Annotated[list, add_messages]


class TestLanggraphDataLoading(
    mixins.TempPathMixin, mixins.DotenvMixin, unittest.TestCase
):
    def test_load_langgraph(self):
        data_filepath = "tests/data/simple.jsonl"
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

                response = graph.invoke(
                    {"messages": ["factor 190,913,277,151"]}, config
                )
                response = graph.invoke(
                    {"messages": ["print them again but reverse the order"]}, config
                )
        self.assertTrue(langgraph_db_path.exists())

        # TODO finish implementing test
        # build an eval that points to langgraph_db_path
        # run the eval
        # verify that the expected data exists in the flexeval database
