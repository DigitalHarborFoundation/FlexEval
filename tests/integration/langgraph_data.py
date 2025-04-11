import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from sympy import primefactors
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


class State(TypedDict):
    messages: Annotated[list, add_messages]


## Define tool
def factor_tool(
    number: Annotated[int, "integer that you need to factor"],
    # number
) -> list:
    """Returns the prime factors of the number as a list of integers"""
    return primefactors(number)


def generate_langgraph_data(
    langgraph_db_path: Path = Path("tests/resources/langgraph-test-data.db"),
):
    ## Create LLM
    tools = [factor_tool]
    llm = ChatOpenAI(model="gpt-4o-mini")
    llm_with_tools = llm.bind_tools(tools)

    def chatbot(state: State):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    ## Build graph
    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools=[factor_tool]))
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,  # this is instead of 'router'.
        # Not entirely clear how it knows which 'tools' node to go to
        # if there are more than 1
        # note that it's missing a dictionary
    )
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.set_entry_point("chatbot")

    langgraph_db_path.unlink(missing_ok=True)

    # Invoke graph - twice
    for i in range(2):
        with SqliteSaver.from_conn_string(str(langgraph_db_path)) as memory:
            graph = graph_builder.compile(checkpointer=memory)

            config = {"configurable": {"thread_id": datetime.now().isoformat()}}

            response = graph.invoke({"messages": ["factor 190,913,277,151"]}, config)
            response = graph.invoke(
                {"messages": ["print them again but reverse the order"]}, config
            )
            for m in response["messages"]:
                logger.info(f"Role: {m.type}")
                logger.info(f"Content: '{m.content}'")


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d (%(funcName)s) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    generate_langgraph_data()
