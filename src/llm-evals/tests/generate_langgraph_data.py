from typing import Annotated
from typing_extensions import TypedDict
from datetime import datetime

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver

from sympy import primefactors
import os

from dotenv import load_dotenv

load_dotenv()


class State(TypedDict):
    messages: Annotated[list, add_messages]


## Define tool
def factor_tool(
    number: Annotated[int, "integer that you need to factor"]
    # number
) -> list:
    """Returns the prime factors of the number as a list of integers"""
    return primefactors(number)


## Create LLM
tools = [factor_tool]
llm = ChatOpenAI(model="gpt-4o")
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

try:
    os.remove("data/langgraph_test_data.db")
except:
    pass

# Invoke graph - twice
for i in range(2):
    with SqliteSaver.from_conn_string("data/langgraph-test-data.db") as memory:
        graph = graph_builder.compile(checkpointer=memory)

        config = {"configurable": {"thread_id": datetime.now().isoformat()}}

        response = graph.invoke({"messages": ["factor 190,913,277,151"]}, config)
        response = graph.invoke(
            {"messages": ["print them again but reverse the order"]}, config
        )
        for m in response["messages"]:
            print("Role:", m.type)
            print(f"Content: '{m.content}'\n")

