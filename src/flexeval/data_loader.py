"""Dataset loading functions. Maybe should move to :mod:`~flexeval.io`."""

import json
import logging
import pathlib
import random as rd
import sqlite3

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from flexeval.classes.dataset import Dataset
from flexeval.classes.message import Message
from flexeval.classes.thread import Thread
from flexeval.classes.tool_call import ToolCall
from flexeval.classes.turn import Turn
from flexeval.schema.evalrun_schema import FileDataSource, FileFormatEnum

logger = logging.getLogger(__name__)


def load_thread_to_dataset(
    thread_id: str | int,
    thread: dict,
    dataset: Dataset,
    eval_run_thread_id: str | None = None,
) -> Thread:
    if "input" not in thread:
        raise ValueError(
            f"Expected thread format is a dictionary containing at least an 'input' key. Instead, we found: {thread.keys()}"
        )

    # extract any metadata
    thread_metadata = thread.copy()
    del thread_metadata["input"]

    context = []
    thread_input = thread["input"]

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
        dataset=dataset,
        jsonl_thread_id=thread_id,
        eval_run_thread_id=eval_run_thread_id,
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
            context.append({"role": role, "content": message.get("content", None)})
            index_in_thread += 1

    add_turns(thread_object)
    return thread_object


def load_file(
    dataset: Dataset,
    data_source: FileDataSource,
    max_n_conversation_threads: int | None = None,
    nb_evaluations_per_thread: int | None = 1,
):
    if data_source.format == FileFormatEnum.jsonl:
        load_jsonl(
            dataset=dataset,
            filename=data_source.path,
            max_n_conversation_threads=max_n_conversation_threads,
            nb_evaluations_per_thread=nb_evaluations_per_thread,
        )
    elif data_source.format == FileFormatEnum.langgraph_sqlite:
        load_langgraph_sqlite(
            dataset=dataset,
            filename=data_source.path,
            max_n_conversation_threads=max_n_conversation_threads,
            nb_evaluations_per_thread=nb_evaluations_per_thread,
        )
    else:
        raise ValueError("Format not yet supported.")


def load_iterable(
    dataset: Dataset,
    iterable,
):
    for thread_id, thread in enumerate(iterable):
        load_thread_to_dataset(thread_id, thread, dataset)


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
            if thread_id in selected_thread_ids:
                thread_json = json.loads(thread)
                for thread_eval_run_id in range(
                    max(1, nb_evaluations_per_thread)
                ):  # duplicate stored threads to enable averaged per-object evaluations
                    eval_run_thread_id = f"{thread_id}_{thread_eval_run_id}"
                    load_thread_to_dataset(
                        thread_id, thread_json, dataset, eval_run_thread_id
                    )

    # TODO - should we add ToolCall here? Is there a standard way to represent them in jsonl?


def load_langgraph_sqlite(
    dataset: Dataset,
    filename: str,
    max_n_conversation_threads: int | None = None,
    nb_evaluations_per_thread: int | None = 1,
):
    """Load conversations from a LangGraph SQLite checkpoint database.

    Reads the final checkpoint for each thread and extracts the cumulative
    message list from channel_values.messages. Compatible with langgraph >= 1.0.
    """
    serializer = JsonPlusSerializer()

    with sqlite3.connect(filename) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        verify_checkpoints_table_exists(cursor)

        cursor.execute("PRAGMA wal_checkpoint(FULL);")

        # Get distinct thread IDs
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
        thread_ids = cursor.fetchall()

        nb_threads = len(thread_ids)
        if max_n_conversation_threads is None:
            max_n_conversation_threads = nb_threads

        if max_n_conversation_threads <= nb_threads:
            selected_thread_ids = rd.sample(thread_ids, max_n_conversation_threads)
        else:
            logger.debug(
                f"You requested up to '{max_n_conversation_threads}' conversations "
                f"but only '{nb_threads}' are present in Sqlite dataset at '{filename}'."
            )
            selected_thread_ids = thread_ids

        for thread_eval_run_id in range(max(1, nb_evaluations_per_thread)):
            for thread_id_row in selected_thread_ids:
                lg_thread_id = thread_id_row[0]

                # Get the final checkpoint (highest step) for this thread
                cursor.execute(
                    """
                    SELECT *, json_extract(metadata, '$.step') as step
                    FROM checkpoints
                    WHERE thread_id = ?
                    ORDER BY json_extract(metadata, '$.step') DESC
                    LIMIT 1
                    """,
                    (lg_thread_id,),
                )
                final_row = cursor.fetchone()
                if final_row is None:
                    logger.warning(f"No checkpoints found for thread '{lg_thread_id}'")
                    continue

                checkpoint = serializer.loads_typed(
                    (final_row["type"], final_row["checkpoint"])
                )
                lg_messages = checkpoint.get("channel_values", {}).get("messages", [])

                if not lg_messages:
                    logger.warning(
                        f"No messages in final checkpoint for thread '{lg_thread_id}'"
                    )
                    continue

                thread = Thread.create(
                    dataset=dataset,
                    langgraph_thread_id=lg_thread_id,
                    eval_run_thread_id=f"{lg_thread_id}_{thread_eval_run_id}",
                )

                # Map message types to FlexEval roles
                # Tools are counted as assistant per existing convention
                context = []
                system_prompt = None
                tool_calls_dict = {}
                tool_responses_dict = {}
                tool_additional_kwargs_dict = {}

                for index_in_thread, msg in enumerate(lg_messages):
                    msg_type = msg.type  # 'human', 'ai', 'tool'
                    role = "user" if msg_type == "human" else "assistant"
                    content = msg.content

                    # Extract tool call info
                    tool_calls = getattr(msg, "tool_calls", []) or []
                    tool_call_ids = [tc["id"] for tc in tool_calls]
                    response_meta = getattr(msg, "response_metadata", {}) or {}
                    token_usage = response_meta.get("token_usage", {})
                    additional_kwargs = getattr(msg, "additional_kwargs", {}) or {}

                    Message.create(
                        dataset=dataset,
                        thread=thread,
                        index_in_thread=index_in_thread,
                        role=role,
                        content=content,
                        context=json.dumps(context),
                        is_flexeval_completion=False,
                        system_prompt=system_prompt,
                        # language model stats
                        tool_calls=json.dumps(tool_calls),
                        tool_call_ids=tool_call_ids,
                        n_tool_calls=len(tool_calls),
                        prompt_tokens=token_usage.get("prompt_tokens"),
                        completion_tokens=token_usage.get("completion_tokens"),
                        model_name=response_meta.get("model_name"),
                        # langgraph metadata
                        langgraph_ts=checkpoint.get("ts"),
                        langgraph_thread_id=lg_thread_id,
                        langgraph_checkpoint_id=final_row["checkpoint_id"],
                        langgraph_parent_checkpoint_id=final_row[
                            "parent_checkpoint_id"
                        ],
                        langgraph_metadata=final_row["metadata"],
                        langgraph_message_type=msg_type,
                        langgraph_type=msg_type,
                    )

                    # Build context for next message
                    context.append({"role": role, "content": content})

                    # Track tool calls and responses for ToolCall creation
                    if msg_type == "tool":
                        tool_call_id = getattr(msg, "tool_call_id", None)
                        if tool_call_id:
                            tool_responses_dict[tool_call_id] = content
                    else:
                        for tc in tool_calls:
                            tool_calls_dict[tc["id"]] = tc
                            tool_additional_kwargs_dict[tc["id"]] = additional_kwargs

                # Create turns from messages
                add_turns(thread)

                # Create ToolCall objects by matching calls to responses
                for tool_call_id, tool_call_vals in tool_calls_dict.items():
                    if tool_call_id not in tool_responses_dict:
                        raise ValueError(
                            f"Found a tool call without a tool response! id='{tool_call_id}'"
                        )
                    matching_message = [
                        m
                        for m in thread.messages
                        if tool_call_id in (m.tool_call_ids or [])
                    ][0]

                    ToolCall.create(
                        dataset=dataset,
                        thread=thread,
                        turn=matching_message.turn,
                        message=matching_message,
                        function_name=tool_call_vals.get("name"),
                        args=json.dumps(tool_call_vals.get("args")),
                        additional_kwargs=json.dumps(
                            tool_additional_kwargs_dict.get(tool_call_id)
                        ),
                        tool_call_id=tool_call_id,
                        response_content=tool_responses_dict.get(tool_call_id),
                    )


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
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='checkpoints'
        """)
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
