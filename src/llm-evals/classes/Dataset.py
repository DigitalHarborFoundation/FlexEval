from classes.BaseModel import BaseModel
from classes.EvalSetRun import EvalSetRun
from classes.Message import Message
from classes.Thread import Thread
from classes.Turn import Turn
import json
import peewee as pw
import sqlite3
import copy
from pprint import pprint
from collections import OrderedDict
from datetime import datetime


class Dataset(BaseModel):
    """Holds a dataset, e.g. a jsonl file"""

    id = pw.IntegerField(primary_key=True)
    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="datasets")
    filename = pw.TextField()
    datatype = pw.TextField(null=True)
    contents = pw.TextField(null=True)  # raw contents

    # Thread - conversation
    # Turn - groups messages (like an 'invocation')
    #
    # Message - content
    #   message_id
    #   turn_id
    # ToolCall - message might have one, but also want the response
    #   message_id
    #   turn_id

    def load_data(self):

        if self.filename.endswith(".jsonl"):
            self.load_jsonl()
        elif is_sqlite_file(self.filename):
            self.load_langgraph_sqlite()
        else:
            raise Exception(
                f"Each Data File must be either a jsonl or sqlite file. You provided the file: {self.filename}"
            )

    def load_jsonl(self):

        self.datatype = "jsonl"
        with open(self.filename, "r") as infile:
            self.contents = infile.read()  # will be a big string

            # Each row is a single row of the jsonl file
            # That means it has 'input' as a key, and a list of dictionaries as values
            conversations = []
            # per line
            for thread in self.contents.splitlines():
                thread = Thread.create(evalsetrun=self.evalsetrun, dataset=self.id)

                message_list = []
                # iterates through the 'input' list
                for message in json.loads(thread)["input"]:
                    data = OrderedDict(
                        {
                            "thread_id": thread.id,
                            "role": message.get("role", None),
                            "content": message.get("content", None),
                            "metadata_json": message.get(
                                "metadata", None
                            ),  # placeholder
                        }
                    )
                    message_list.append(data)

                # Make a Thread for each
                # Step 1 - add grouping variable for turns
                message_list = set_turn_id(input_list=message_list)
                # Step 2 - get list of grouping variables
                placeholder_turn_ids = set([m["turn_id"] for m in message_list])
                # Step 3 - do 'group by' and create a turn for each group
                for placeholder_id in placeholder_turn_ids:
                    turn = Turn.create(
                        evalsetrun=self.evalsetrun, dataset=self.id, thread=thread.id
                    )
                    # Step 4 - create the messages that belong to this turn
                    messages_in_turn = [
                        m for m in message_list if m["turn_id"] == placeholder_id
                    ]
                    for message in messages_in_turn:
                        Message.create(
                            evalsetrun=self.evalsetrun,
                            dataset=self.id,
                            thread=thread.id,
                            turn=turn.id,
                            role=message.get("role", None),
                            content=message.get("content", None),
                            metadata=message.get("metadata", None),
                            is_final_turn_in_input=message.get(
                                "is_final_turn_in_input", False
                            ),
                            is_completion=False,
                        )

        # TODO - should we add ToolCall here? Is there a standard way to represent them in jsonl?

    def load_langgraph_sqlite(self):

        self.datatype = "langgraph"
        with sqlite3.connect(self.filename) as conn:
            # Create a cursor object
            cursor = conn.cursor()

            # check that the 'checkpoints' table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='checkpoints'
                """
            )
            result = cursor.fetchone()
            # Assert that the result is not None, meaning the table exists
            assert (
                result is not None
            ), f"Table 'checkpoints' does not exist in the database."

            # Make threads
            query = "select distinct thread_id from checkpoints"
            cursor.execute(query)
            thread_ids = cursor.fetchall()
            for thread_id in thread_ids:
                thread = Thread.create(
                    evalsetrun=self.evalsetrun,
                    dataset=self.id,
                    langgraph_thread_id=thread_id,
                )

                # get messages associated with that thread, only
                message_list = []
                query = f"select * from checkpoints where thread_id = '{thread.langgraph_thread_id}'"
                cursor.execute(query)
                messages = cursor.fetchall()

                # iterates through the 'input' list
                for message_row in messages:
                    checkpoint = json.loads(message_row[4])
                    metadata = json.loads(message_row[5])

                    data = OrderedDict(
                        {
                            "thread_id": row[0],
                            "conversation_id": row[0],  # same as conversation_id
                            "thread_ts": row[1],
                            "parent_ts": row[2],
                            "ts": checkpoint.get("ts", None),
                            "id": checkpoint.get("id", None),
                            # these two are the same
                            "invocation_id": checkpoint.get("channel_values", {}).get(
                                "invocation_id", None
                            ),
                            "turn_id": checkpoint.get("channel_values", {}).get(
                                "invocation_id", None
                            ),
                        }
                    )

                    data = OrderedDict(
                        {
                            "thread_id": thread.id,
                            "role": message.get("role", None),
                            "content": message.get("content", None),
                            "metadata_json": message.get(
                                "metadata", None
                            ),  # placeholder
                        }
                    )
                    message_list.append(data)

                # Make a Thread for each
                # Step 1 - add grouping variable for turns
                message_list = set_turn_id(input_list=message_list)
                # Step 2 - get list of grouping variables
                placeholder_turn_ids = set([m["turn_id"] for m in message_list])
                # Step 3 - do 'group by' and create a turn for each group
                for placeholder_id in placeholder_turn_ids:
                    turn = Turn.create(
                        evalsetrun=self.evalsetrun, dataset=self.id, thread=thread.id
                    )
                    # Step 4 - create the messages that belong to this turn
                    messages_in_turn = [
                        m for m in message_list if m["turn_id"] == placeholder_id
                    ]
                    for message in messages_in_turn:
                        Message.create(
                            evalsetrun=self.evalsetrun,
                            dataset=self.id,
                            thread=thread.id,
                            turn=turn.id,
                            role=message.get("role", None),
                            content=message.get("content", None),
                            metadata=message.get("metadata", None),
                            is_final_turn_in_input=message.get(
                                "is_final_turn_in_input", False
                            ),
                            is_completion=False,
                        )

            #

            # turn = Turn.create(
            #             evalsetrun=self.evalsetrun, dataset=self.id, thread=thread.id
            #         )
            # Message.create(
            #                 evalsetrun=self.evalsetrun,
            #                 dataset=self.id,
            #                 thread=thread.id,
            #                 turn=turn.id,
            #                 role=message.get("role", None),
            #                 content=message.get("content", None),
            #                 metadata=message.get("metadata", None),
            #                 is_final_turn_in_input=message.get(
            #                     "is_final_turn_in_input", False
            #                 ),
            #                 is_completion=False,
            #             )
            # Iterate through each row of the database
            # Each row has a thread_id that defines its thread

            current_thread_id = ""
            message_list = []
            for ix, row in enumerate(self.contents):
                thread_id = row[0]

                # Create a new thread if you have a new ID
                if thread_id != current_thread_id:
                    current_thread_id = thread_id
                    thread = Thread.create(
                        evalsetrun=self.evalsetrun,
                        dataset=self.id,
                        langgraph_thread_id=current_thread_id,
                    )

                # Create a list of messages, and then we can add metadata and create the objects
                # iterates through the 'input' list
                for message in json.loads(thread)["input"]:
                    data = OrderedDict(
                        {
                            "thread_id": thread.id,
                            "role": message.get("role", None),
                            "content": message.get("content", None),
                            "metadata_json": message.get(
                                "metadata", None
                            ),  # placeholder
                        }
                    )
                    message_list.append(data)

                checkpoint = json.loads(row[3])
                metadata = json.loads(row[4])
                data = OrderedDict(
                    {
                        "thread_id": row[0],
                        "conversation_id": row[0],  # same as conversation_id
                        "thread_ts": row[1],
                        "parent_ts": row[2],
                        "ts": checkpoint.get("ts", None),
                        "id": checkpoint.get("id", None),
                        # these two are the same
                        "invocation_id": checkpoint.get("channel_values", {}).get(
                            "invocation_id", None
                        ),
                        "turn_id": checkpoint.get("channel_values", {}).get(
                            "invocation_id", None
                        ),
                    }
                )
                if metadata.get("writes", {}) is None:
                    # just skip this entry - there is no state update so we don't need to analyze it
                    continue
                for node, entry in metadata.get("writes", {}).items():
                    data_1 = copy.deepcopy(data)
                    if node == "messages":  # was a human input
                        data_1["role"] = "human"
                        data_1["node"] = "human"
                        data_1["content"] = entry[0].get("content", "")
                        input.append(data_1)

                    elif (
                        "messages" in entry
                        and isinstance(entry["messages"], list)
                        and len(entry["messages"]) > 0
                    ):  # is a chatbot message update
                        for message in entry["messages"]:
                            data_2 = copy.deepcopy(data_1)
                            data_2["role"] = "ai"
                            data_2["node"] = node
                            data_2["name"] = message.get("kwargs", {}).get("name", None)
                            data_2["message_id"] = message.get("kwargs", {}).get(
                                "id", None
                            )
                            data_2["kwargs_json"] = message.get("kwargs", None)
                            data_2["type"] = message.get("kwargs", {}).get("type", None)
                            data_2["content"] = message.get("kwargs", {}).get(
                                "content", None
                            )
                            data_2["metadata_json"] = message.get("kwargs", {}).get(
                                "response_metadata", None
                            )
                            data_2["prompt_tokens"] = (
                                message.get("kwargs", {})
                                .get("response_metadata", {})
                                .get("token_usage", {})
                                .get("prompt_tokens", None)
                            )
                            data_2["completion_tokens"] = (
                                message.get("kwargs", {})
                                .get("response_metadata", {})
                                .get("token_usage", {})
                                .get("completion_tokens", None)
                            )
                            data_2["model_name"] = (
                                message.get("kwargs", {})
                                .get("response_metadata", {})
                                .get("model_name", None)
                            )
                            data_2["finish_reason"] = (
                                message.get("kwargs", {})
                                .get("response_metadata", {})
                                .get("finish_reason", None)
                            )
                            data_2["tool_call_id"] = message.get("kwargs", {}).get(
                                "tool_call_id", None
                            )
                            # make a different entry for each tool call
                            if (
                                len(message.get("kwargs", {}).get("tool_calls", []))
                                == 0
                            ):
                                input.append(data_2)

                            else:
                                for tool_call in message.get("kwargs", {}).get(
                                    "tool_calls", []
                                ):
                                    data_3 = copy.deepcopy(data_2)
                                    data_3["tool_name"] = tool_call.get("name", None)
                                    data_3["tool_args"] = tool_call.get("args", None)
                                    data_3["tool_call_id"] = tool_call.get("id", None)
                                    input.append(data_3)

            # add latency information
            for entry in input:
                if entry["role"] == "human":
                    human_timestamp = entry["ts"]
                    entry["latency_in_seconds"] = None
                else:
                    entry["latency_in_seconds"] = (
                        datetime.fromisoformat(entry["ts"])
                        - datetime.fromisoformat(human_timestamp)
                    ).total_seconds()

            for entry in input:
                pprint(entry, indent=4)

        # group into conversations
        thread_ids = set([i["thread_id"] for i in input])
        conversations = [
            {"input": [i for i in input if i["thread_id"] == thread_id]}
            for thread_id in thread_ids
        ]

        return conversations


def set_turn_id(input_list: list):
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

    input_list = copy.deepcopy(input_list)
    turn_id = 1
    previous_role = ""

    for turnentry_id, entry in enumerate(input_list):
        current_role = entry.get("role", None)

        # if your role matches a previous, don't increment turn_id
        if (current_role in machine_labels and previous_role in machine_labels) or (
            current_role not in machine_labels and previous_role not in machine_labels
        ):
            previous_role = current_role
            entry["turn_id"] = turn_id
        else:
            turn_id += 1
            entry["turn_id"] = turn_id
            previous_role = current_role

    # label final entry
    for entry in input_list:
        if entry["turn_id"] == turn_id:
            entry["is_final_turn_in_input"] = True
        else:
            entry["is_final_turn_in_input"] = False
    assert input_list[-1]["is_final_turn_in_input"] is True
    for entry in input_list:
        assert "turn_id" in entry

    return input_list


def is_sqlite_file(filepath):
    # Open the file in binary mode
    with open(filepath, "rb") as file:
        header = file.read(16)
    # Check if the header matches the SQLite format header
    return header == b"SQLite format 3\x00"
