"""Dataset loading functions. Maybe should move to :mod:`~flexeval.io`."""

import json
import logging
import pathlib
import random as rd
import sqlite3

from langchain.load.dump import dumps
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from flexeval.classes.dataset import Dataset
from flexeval.classes.message import Message
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn

logger = logging.getLogger(__name__)


def load_jsonl(
    dataset: Dataset,
    filename: str | pathlib.Path,
    max_n_conversation_threads: int | None = None,
    nb_evaluations_per_thread: int | None = 1,
):
    with open(filename, "r") as infile:
        contents = infile.read()  # will be a big string
        all_lines = contents.splitlines()

        # Each row is a single row of the jsonl file
        # That means it has 'input' as a key, and a list of dictionaries as values
        # per line

        if max_n_conversation_threads is None:
            max_n_conversation_threads = len(all_lines)

        if max_n_conversation_threads <= len(all_lines):
            selected_thread_ids = rd.sample(
                list(range(len(all_lines))), max_n_conversation_threads
            )
        else:
            logger.debug(
                f"You requested up to '{max_n_conversation_threads}' conversations but only '{len(all_lines)}' are present in Jsonl dataset at '{filename}'."
            )
            selected_thread_ids = list(range(len(all_lines)))

        ### should duplicate the select threads nb_evaluations_per_thread times
        if nb_evaluations_per_thread is None:
            nb_evaluations_per_thread = 1

        for thread_id, thread in enumerate(all_lines):
            for thread_eval_run_id in range(
                max(1, nb_evaluations_per_thread)
            ):  # duplicate stored threads for averaged evaluation results
                if thread_id in selected_thread_ids:
                    thread_json = json.loads(thread)
                    # extract any metadata
                    thread_metadata = thread_json.copy()
                    del thread_metadata["input"]

                    context = []
                    thread_input = thread_json["input"]

                    # Get system prompt used in the thread - assuming only 1
                    for message in thread_input:
                        if message["role"] == "system":
                            system_prompt = message["content"]
                            break
                    else:
                        system_prompt = None
                    if system_prompt is not None:
                        # Add the system prompt as context
                        context.append({"role": "system", "content": system_prompt})

                    thread_object: Thread = Thread.create(
                        evalsetrun=dataset.evalsetrun,
                        dataset=dataset,
                        jsonl_thread_id=thread_id,
                        eval_run_thread_id=str(thread_id)
                        + "_"
                        + str(thread_eval_run_id),
                        system_prompt=system_prompt,
                        metadata=json.dumps(thread_metadata),
                    )

                    # Create messages
                    index_in_thread = 0
                    for message in thread_input:
                        if not isinstance(message, dict):
                            raise ValueError(
                                f"Can't load unknown object type; expected dict. Check JSONL format: {message}"
                            )
                        role = message.get("role", None)
                        if role != "system":
                            # System message shouldn't be added as a separate message
                            system_prompt_for_this_message = ""
                            if role != "user":
                                system_prompt_for_this_message = system_prompt
                            message_metadata = message.copy()
                            if "content" in message_metadata:
                                del message_metadata["content"]
                            if "role" in message_metadata:
                                del message_metadata["role"]
                            Message.create(
                                evalsetrun=dataset.evalsetrun,
                                dataset=dataset,
                                thread=thread_object,
                                index_in_thread=index_in_thread,
                                role=role,
                                content=message.get("content", None),
                                context=json.dumps(context),
                                is_flexeval_completion=False,
                                system_prompt=system_prompt_for_this_message,
                                metadata=json.dumps(message_metadata),
                            )
                            # Update context
                            context.append(
                                {"role": role, "content": message.get("content", None)}
                            )
                            index_in_thread += 1

                    add_turns(thread_object)

    # TODO - should we add ToolCall here? Is there a standard way to represent them in jsonl?


def load_langgraph_sqlite(
    dataset: Dataset,
    filename: str,
    max_n_conversation_threads: int | None = None,
    nb_evaluations_per_thread: int | None = 1,
):
    serializer = JsonPlusSerializer()

    with sqlite3.connect(filename) as conn:
        # Set the row factory to sqlite3.Row
        # allowing us to reference columns by name instead of index
        conn.row_factory = sqlite3.Row

        # Create a cursor object
        cursor = conn.cursor()
        verify_checkpoints_table_exists(cursor)

        # Sync database
        query = "PRAGMA wal_checkpoint(FULL);"
        cursor.execute(query)

        # Make threads (aka conversations)
        query = "select distinct thread_id from checkpoints"
        cursor.execute(query)
        thread_ids = cursor.fetchall()

        nb_threads = len(thread_ids)
        if max_n_conversation_threads is None:
            max_n_conversation_threads = nb_threads

        if max_n_conversation_threads <= nb_threads:
            selected_thread_ids = rd.sample(thread_ids, max_n_conversation_threads)
        else:
            logger.debug(
                f"You requested up to '{max_n_conversation_threads}' conversations but only '{nb_threads}' are present in Sqlite dataset at '{filename}'."
            )
            selected_thread_ids = thread_ids

        logger.debug(" DEBUG DUPLICATE SELECT THREAD IDS\n", selected_thread_ids[0])

        for thread_eval_run_id in range(
            max(1, nb_evaluations_per_thread)
        ):  # duplicate stored threads for averaged evaluation results
            for thread_id in selected_thread_ids:
                thread = Thread.create(
                    evalsetrun=dataset.evalsetrun,
                    dataset=dataset,
                    langgraph_thread_id=thread_id[0],
                    eval_run_thread_id=str(thread_id[0])
                    + "_"
                    + str(thread_eval_run_id),
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
                tool_addional_kwargs_dict = {}
                # system prompt reset for every thread
                system_prompt = None

                for completion_row in completion_list:
                    # checkpoint is full state history
                    checkpoint = serializer.loads_typed(
                        (completion_row["type"], completion_row["checkpoint"])
                    )
                    # metadata is the state update for that row
                    metadata = json.loads(completion_row["metadata"])
                    # IDs from langgraph

                    if metadata.get("writes") is None:
                        continue
                    else:
                        # Goal here is to create a data structure for EACH write/update
                        # that can be used to construct a Message object
                        # LangGraph stores info in 'writes' in the checkpoints.metadata column
                        # but the format is a bit different between human and machine input
                        # The resulting data structure should have
                        # key (str) -- graph 'node' that produced the message (or 'human')
                        # value (list) -- list of 'message' data structures with id, kwargs, etc
                        # {
                        #   'node_name':{
                        #      "messages":[
                        #          {
                        #             'id': "XYZ"
                        #             'kwargs':{
                        #                 "content": 'text of the message',
                        #                 "additional_kwargs": {}
                        #           },
                        #        }
                        #       ]
                        #
                        #   }
                        # }

                        # user input condition
                        if metadata.get("source") == "input":
                            # NOTE: I think with the updated logging of HumanMessage with langgraph, we don't need this case
                            update_dict = {}
                            # this will be a dictionary we can add to
                            # key is 'input', as in human input
                            update_dict["input"] = {"messages": []}
                            # print("metadata keys:", metadata["writes"].keys())
                            # the very first message in input in a thread seems to include
                            # the system prompt, not a message that was sent by the user.
                            # the system promptdoesn't seem to be set anywhere else, so
                            # using that as the system prompt for the thread.
                            messagecount = 0
                            for msg in metadata["writes"]["__start__"]["messages"]:
                                if messagecount == 0 and metadata["step"] == -1:
                                    system_prompt = msg["kwargs"]["content"]
                                    messagecount += 1
                                else:
                                    message = {}
                                    message["id"] = [
                                        "HumanMessage"
                                    ]  # LangGraph has a list here
                                    message["kwargs"] = {}
                                    message["kwargs"]["content"] = msg
                                    message["kwargs"]["type"] = "human"
                                    update_dict["input"]["messages"].append(message)
                            # will be used below
                            role = "user"

                        # machine input condition
                        elif metadata.get("source") == "loop":
                            # This already has a list of messages with kwargs, etc
                            update_dict = metadata.get("writes")
                            # I think 'system_prompt' is empty by default and not stored here unless
                            # it's included in the LangGraph state
                            checkpoint_system_prompt = checkpoint.get(
                                "channel_values", {}
                            ).get("system_prompt")
                            if checkpoint_system_prompt is not None:
                                system_prompt = checkpoint_system_prompt
                            role = "assistant"
                        else:
                            raise Exception(
                                f"Unhandled input condition! Source not 'loop' or 'input'. Metadata: {metadata}"
                            )
                        # Add system prompt as first thing in context if not already present
                        if len(context) == 0:
                            context.append({"role": "system", "content": system_prompt})

                        # iterate through nodes - there is probably only 1
                        for node, value in update_dict.items():
                            # iterate through list of message updates
                            if "messages" in value:
                                if isinstance(value["messages"], dict):
                                    # Make this a list to iterate through - 4 Feb 2025 - used to be a list previously
                                    messagelist = [value["messages"]]
                                else:
                                    messagelist = value["messages"]
                                index_in_thread = 0
                                for message in messagelist:
                                    if role == "user":
                                        content = (
                                            message.get("kwargs", {})
                                            .get("content", {})
                                            .get("kwargs", {})
                                            .get("content", None)
                                        )
                                    elif role == "assistant":
                                        content = message.get("kwargs", {}).get(
                                            "content", None
                                        )
                                    else:
                                        raise Exception(
                                            "`role` should be either user or assistant."
                                        )
                                    Message.create(
                                        evalsetrun=dataset.evalsetrun,
                                        dataset=dataset,
                                        thread=thread,
                                        index_in_thread=index_in_thread,
                                        role=role,
                                        content=content,
                                        context=json.dumps(context),
                                        is_flexeval_completion=False,
                                        system_prompt=system_prompt,
                                        # language model stats
                                        tool_calls=json.dumps(
                                            message.get("kwargs", {}).get(
                                                "tool_calls", []
                                            )
                                        ),
                                        tool_call_ids=[
                                            tc["id"]
                                            for tc in message.get("kwargs", {}).get(
                                                "tool_calls", []
                                            )
                                        ],
                                        n_tool_calls=len(
                                            message.get("kwargs", {}).get(
                                                "tool_calls", []
                                            )
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
                                        langgraph_ts=checkpoint.get("ts"),
                                        langgraph_step=metadata.get("step"),
                                        langgraph_thread_id=completion_row["thread_id"],
                                        langgraph_checkpoint_id=completion_row[
                                            "checkpoint_id"
                                        ],
                                        langgraph_parent_checkpoint_id=completion_row[
                                            "parent_checkpoint_id"
                                        ],
                                        langgraph_checkpoint=dumps(
                                            checkpoint
                                        ),  # Have to re-dump this because of the de-serialization#completion_row["checkpoint"],
                                        langgraph_metadata=completion_row["metadata"],
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
                                    context.append(
                                        {
                                            "role": role,
                                            "content": content,
                                            "langgraph_role": message["id"][-1],
                                        }
                                    )

                                    # record tool call info so we can match them up later
                                    if message.get("kwargs", {}).get("type") == "tool":
                                        # this should have a mapping between tool_call_id and the RESPONSE to to the tool call
                                        tool_responses_dict[
                                            message.get("kwargs", {}).get(
                                                "tool_call_id"
                                            )
                                        ] = message.get("kwargs", {}).get("content", "")
                                    else:
                                        for tool_call in message.get("kwargs", {}).get(
                                            "tool_calls", []
                                        ):
                                            # this should have all the info about the tool calls, including additional_kwargs
                                            # but NOT their responses
                                            tool_calls_dict[tool_call["id"]] = tool_call
                                            tool_addional_kwargs_dict[
                                                tool_call["id"]
                                            ] = message.get("kwargs", {}).get(
                                                "additional_kwargs", {}
                                            )
                                    index_in_thread += 1

                # Add turns to each message
                # Need to do this before dealing with tool calls, since we
                # associated turns with tool calls via messages during the .create() method
                add_turns(thread)

                ## Match up tool calls and make an object for each match
                for tool_call_id, tool_call_vals in tool_calls_dict.items():
                    if tool_call_id not in tool_responses_dict:
                        raise ValueError(
                            f"Found a tool call without a tool response! id='{tool_call_id}'"
                        )
                    # get matching message - should now be accessible through thread now?
                    matching_message = [
                        m for m in thread.messages if tool_call_id in m.tool_call_ids
                    ][0]

                    ToolCall.create(
                        evalsetrun=dataset.evalsetrun,
                        dataset=dataset,
                        thread=thread,
                        turn=matching_message.turn,
                        message=matching_message,
                        function_name=tool_call_vals.get("name"),
                        args=json.dumps(tool_call_vals.get("args")),
                        additional_kwargs=json.dumps(
                            tool_addional_kwargs_dict.get(tool_call_id)
                        ),
                        tool_call_id=tool_call_id,
                        response_content=tool_responses_dict.get(tool_call_id),
                    )

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
    index_in_thread = 0
    for placeholder_turn_id, role in turn_dict.items():  # turns.items():
        t = Turn.create(
            evalsetrun=thread.evalsetrun,
            dataset=thread.dataset,
            thread=thread,
            index_in_thread=index_in_thread,
            role=role,
        )
        # map placeholder id to turn object
        turns[placeholder_turn_id] = t
        index_in_thread += 1
    # Step 3 - add placeholder ids to messages
    # Can use zip since entries in message_list correspond to thread.messages
    # NOTE: ANR: I don't follow how the message_list was supposed to work below.
    for ml, message in zip(message_placeholder_ids, thread.messages):
        # Is this going to work? No idea
        message.turn = turns[ml]
        # message.is_final_turn_in_input = ml.get("is_final_turn_in_input", False)
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
    assert result is not None, "Table 'checkpoints' does not exist in the database."


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
    for turnentry_id, entry in enumerate(thread.messages):  # enumerate(input_list):
        current_role = entry.role  # entry.get("role", None)
        # entry["role"] = current_role
        # if your role matches a previous, don't increment turn_id
        if (current_role in machine_labels and previous_role in machine_labels) or (
            current_role not in machine_labels and previous_role not in machine_labels
        ):
            pass  # TODO: clean up the condition to avoid the empty if
            # previous_role = current_role
            # entry["placholder_turn_id"] = turn_id
        else:
            turn_id += 1
            # entry["placholder_turn_id"] = turn_id
            # previous_role = current_role
        # entry.turn_id = turn_id
        message_placeholder_ids.append(turn_id)
        previous_role = current_role
        # entry.save()

    # NOTE: ANR seems like this could be optimized - e.g., set all
    # to false, then do a select query for just the ones where turn_id column is turn_id. That would also
    # reduce the number of saves to the database.
    # label final entry
    # ANR: moved up the turn_id_roles bit here to avoid iterating twice
    turn_id_roles = {}
    for message_placehold_id, entry in zip(
        message_placeholder_ids, thread.messages
    ):  # input_list:
        turn_id_roles[message_placehold_id] = entry.role
        entry.is_final_turn_in_input = message_placehold_id == turn_id
        entry.save()  # Could optimize this to avoid saving twice

    return message_placeholder_ids, turn_id_roles
