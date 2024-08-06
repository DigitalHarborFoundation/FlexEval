import json
import copy
import sqlite3

from typing import OrderedDict
from classes.Thread import Thread
from classes.Turn import Turn
from classes.Message import Message
from classes.ToolCall import ToolCall


def load_jsonl(dataset, filename):

    with open(filename, "r") as infile:
        contents = infile.read()  # will be a big string

        # Each row is a single row of the jsonl file
        # That means it has 'input' as a key, and a list of dictionaries as values
        # per line
        for thread in contents.splitlines():
            thread = Thread.create(evalsetrun=dataset.evalsetrun, dataset=dataset)

            # Get system prompt used in the thread - assuming only 1
            system_prompt = [
                i["content"]
                for i in json.loads(thread)["input"]
                if i["role"] == "system"
            ][0]
            # Create messages
            for message in json.loads(thread)["input"]:

                Message.create(
                    evalsetrun=dataset.evalsetrun,
                    dataset=dataset,
                    thread=thread,
                    role=message.get("role", None),
                    content=message.get("content", None),
                    metadata=message.get("metadata", None),
                    is_flexeval_completion=False,
                    system_prompt=system_prompt,
                )

            add_turns(thread)

    # TODO - should we add ToolCall here? Is there a standard way to represent them in jsonl?


def load_langgraph_sqlite(dataset, filename):

    with sqlite3.connect(filename) as conn:
        # Create a cursor object
        cursor = conn.cursor()
        verify_checkpoints_table_exists(cursor)

        # Make threads (aka conversations)
        query = "select distinct thread_id from checkpoints"
        cursor.execute(query)
        thread_ids = cursor.fetchall()
        for thread_id in thread_ids:
            thread = Thread.create(
                evalsetrun=dataset.evalsetrun,
                dataset=dataset,
                langgraph_thread_id=thread_id[0],
            )

            # Create messages
            query = f"select * from checkpoints where thread_id = '{thread.langgraph_thread_id}'"
            cursor.execute(query)
            completion_list = cursor.fetchall()

            # context has to be reset at the start of every thread
            context = []
            # tool call variables
            tool_calls_dict = {}
            tool_responses_dict = {}
            for completion_row in completion_list:
                # checkpoint is full state history
                checkpoint = json.loads(completion_row[3])
                # metadata is the state update for that row
                metadata = json.loads(completion_row[4])
                # IDs from langgraph

                if metadata.get("writes") is None:
                    continue
                else:
                    # user input condition
                    if metadata.get("source") == "input":
                        #NOTE: I think with the updated logging of HumanMessage with langgraph, we don't need this case
                        update_dict = {}
                        update_dict["input"] = metadata.get("writes")#.get("messages")
                        for message in update_dict["input"]["messages"]:
                            message["id"] = ["HumanMessage"]
                            message['kwargs'] = {}
                            message['kwargs']['content'] = message['content']
                        role = "user"
                        system_prompt = None
                    # machine input condition
                    elif metadata.get("source") == "loop":
                        update_dict = metadata.get("writes")
                        # assume system prompt is part of the state
                        system_prompt = checkpoint.get("channel_values", {}).get(
                            "system_prompt"
                        )
                        role = "assistant"
                    else:
                        raise Exception(
                            f"Unhandled input condition! here is the metadata: {metadata}"
                        )
                    # Add system prompt as first thing in context if not already present
                    if len(context) == 0:
                        context.append({'role' : 'system', 'content' : system_prompt})

                    # iterate through nodes - there is probably only 1
                    for node, value in update_dict.items():
                        # iterate through list of message updates
                        if "messages" in value:
                            for message in value["messages"]:
                                content = message.get("kwargs", {}).get(
                                        "content", None
                                    )
                                Message.create(
                                    evalsetrun=dataset.evalsetrun,
                                    dataset=dataset,
                                    thread=thread,
                                    role=role,
                                    content=content,
                                    context=json.dumps(context),
                                    is_flexeval_completion=False,
                                    system_prompt=system_prompt,
                                    # language model stats
                                    tool_calls=json.dumps(
                                        message.get("kwargs", {}).get("tool_calls", [])
                                    ),
                                    tool_call_ids=[
                                        tc["id"]
                                        for tc in message.get("kwargs", {}).get(
                                            "tool_calls", []
                                        )
                                    ],
                                    n_tool_calls=len(
                                        message.get("kwargs", {}).get("tool_calls", [])
                                    ),
                                    prompt_tokens=message.get("kwargs", {})
                                    .get("response_metadata", {})
                                    .get("token_usage", {})
                                    .get("prompt_tokens"),
                                    completion_tokens=message.get("kwargs", {})
                                    .get("response_metadata", {})
                                    .get("token_usage", {})
                                    .get("completion_tokens"),
                                    model_name=message.get("kwargs", {})
                                    .get("response_metadata", {})
                                    .get("model_name"),
                                    # langgraph metadata
                                    langgraph_step=metadata.get("step"),
                                    langgraph_checkpoint_ts=checkpoint.get("ts", None),
                                    langgraph_checkpoint_id=checkpoint.get("id", None),
                                    langgraph_thread_id=completion_row[0],
                                    langgraph_thread_ts=completion_row[1],
                                    langgraph_parent_ts=completion_row[2],
                                    langgraph_checkpoint=completion_row[3],
                                    langgraph_metadata=completion_row[4],
                                    langgraph_node=node,
                                    langgraph_message_type=message["id"][-1],
                                    langgraph_type=message.get("kwargs", {}).get(
                                        "type"
                                    ),
                                    # special property of state
                                    langchain_print=message.get("kwargs", {})
                                    .get("additional_kwargs", {})
                                    .get("print", False),
                                )

                                # update the context for the next Message
                                context.append({'role' : role, 'content' : content})

                                # record tool call info so we can match them up later
                                if message.get("kwargs", {}).get("type") == "tool":
                                    tool_responses_dict[
                                        message.get("kwargs", {}).get("tool_call_id")
                                    ] = message.get("kwargs", {}).get("content", "")
                                else:
                                    for tool_call in message.get("kwargs", {}).get(
                                        "tool_calls", []
                                    ):
                                        tool_calls_dict[tool_call["id"]] = tool_call
            ## Match up tool calls and make an object for each match
            for tool_call_id, tool_call_vals in tool_calls_dict.items():
                assert (
                    tool_call_id in tool_responses_dict
                ), f"Found a tool call without a tool response! id: {tool_call_id}"
                ToolCall.create(
                    evalsetrun=dataset.evalsetrun,
                    dataset=dataset,
                    thread=thread,
                    # get matching message - should now be accessible through thread now?
                    message=[
                        m for m in thread.messages if tool_call_id in m.tool_call_ids
                    ][0],
                    function_name=tool_call_vals.get("name"),
                    args=json.dumps(tool_call_vals.get("args")),
                    tool_call_id=tool_call_id,
                    response_content=tool_responses_dict.get(tool_call_id),
                )

            add_turns(thread)

            ## Add system prompt if available?


def add_turns(thread: Thread):
    # Add turn labels
    # Step 1 - add placeholder_turn_id to each message
    message_roles = []
    for message in thread.messages:
        message_roles.append({"id": message.id, "role": message.role})
    message_placeholder_ids, turn_dict = get_turns(thread=thread)
    # Step 2 - Create turns, plus a mapping between the placeholder ids and the created ids
    turns = {}
    for placeholder_turn_id, role in turn_dict.items():#turns.items():
        t = Turn.create(
            evalsetrun=thread.evalsetrun, dataset=thread.dataset, thread=thread, role=role
        )
        # map placeholder id to turn object
        turns[placeholder_turn_id] = t
    # Step 3 - add placeholder ids to messages
    # Can use zip since entries in message_list correspond to thread.messages
    # NOTE: ANR: I don't follow how the message_list was supposed to work below.
    for ml, message in zip(message_placeholder_ids, thread.messages):
        # Is this going to work? No idea
        message.turn = turns[ml]
        #message.is_final_turn_in_input = ml.get("is_final_turn_in_input", False)
        message.save()
    


def verify_checkpoints_table_exists(cursor):
    # double check that the 'checkpoints' table exists
    cursor.execute(
        """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='checkpoints'
        """
    )
    result = cursor.fetchone()
    # Assert that the result is not None, meaning the table exists
    assert result is not None, f"Table 'checkpoints' does not exist in the database."


def get_turns(thread: Thread):
    """We're defining a turn as a list of 1 or more consequtive outputs
    by the same role, where the role is either 'user', or 'assistant/tool'.
    In other words, we would parse as follows:
    TURN 1 - user
    TURN 2 - assistant
    TURN 3 - user
    TURN 4 - assistant
    TURN 4 - tool
    TURN 4 - assistant
    TURN 5 - user
    """

    # these are all treated as belonging to the same 'turn'
    machine_labels = ["assistant", "ai", "tool"]

    turn_id = 1
    previous_role = ""
    # TODO: Make a message list here, store the placeholder ids, and update to the real turn ids; save at end
    message_placeholder_ids = []
    for turnentry_id, entry in enumerate(thread.messages):#enumerate(input_list):
        current_role = entry.role #entry.get("role", None)
        #entry["role"] = current_role
        # if your role matches a previous, don't increment turn_id
        if (current_role in machine_labels and previous_role in machine_labels) or (
            current_role not in machine_labels and previous_role not in machine_labels
        ):
            pass # TODO: clean up the condition to avoid the empty if
            #previous_role = current_role
            #entry["placholder_turn_id"] = turn_id
        else:
            turn_id += 1
            #entry["placholder_turn_id"] = turn_id
            #previous_role = current_role
        #entry.turn_id = turn_id
        message_placeholder_ids.append(turn_id)
        previous_role = current_role
        #entry.save()

    #NOTE: ANR seems like this could be optimized - e.g., set all
    # to false, then do a select query for just the ones where turn_id column is turn_id. That would also
    # reduce the number of saves to the database.
    # label final entry
    # ANR: moved up the turn_id_roles bit here to avoid iterating twice
    turn_id_roles = {}
    for message_placehold_id, entry in zip(message_placeholder_ids, thread.messages): #input_list:
        turn_id_roles[message_placehold_id] = entry.role
        entry.is_final_turn_in_input = message_placehold_id == turn_id
        entry.save() # Could optimize this to avoid saving twice

    return message_placeholder_ids, turn_id_roles

