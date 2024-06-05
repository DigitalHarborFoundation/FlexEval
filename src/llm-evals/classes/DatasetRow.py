from classes.BaseModel import BaseModel
from classes.Dataset import Dataset
from classes.EvalSetRun import EvalSetRun
import json
import peewee as pw
import copy


class DatasetRow(BaseModel):
    """Class for holding a single row of a dataset, i.e. one conversation"""

    id = pw.IntegerField(primary_key=True)
    dataset = pw.ForeignKeyField(Dataset, backref="rows")
    evalsetrun = pw.ForeignKeyField(EvalSetRun, backref="rows")
    input = pw.TextField()
    ideals = pw.TextField(
        null=True
    )  # dictionary mapping between eval name and ideal value
    metadata = pw.TextField(
        null=True
    )  # dictionary - this is all other info besides input and ideals

    def get_turns(self):
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
        input_list = json.loads(self.input)
        parsed_input = []
        previous_role = ""
        previous_turn = []

        if input_list[0].get("role") == "system":
            system_prompt = input_list[0].get("content")
            offset = 1
        else:
            system_prompt = ""
            offset = 0

        for ix, entry in enumerate(input_list[offset:]):
            current_turn = [copy.deepcopy(entry)]  # list of length 1
            current_role = entry.get("role")

            # if there is no previous role to append to, just continue
            if len(previous_turn) == 0:
                previous_turn += current_turn
                previous_role = current_role

            # if your role matches a previous, accumulate
            elif (current_role == "user" and previous_role == "user") or (
                current_role in ["assistant", "tool"]
                and previous_role in ["assistant", "tool"]
            ):
                previous_turn = copy.deepcopy(previous_turn + current_turn)  # add lists
                previous_role = current_role

            # if you have a different role than the previous,
            # add the previous to the list and create a new turn
            else:
                parsed_input.append(
                    {
                        "role": "user" if previous_role == "user" else "assistant",
                        "turn": previous_turn,
                        "tool_used": (
                            True  # TODO - specify more info
                            if any(["tool" in i["role"] for i in previous_turn])
                            else ""
                        ),
                        "system_prompt": system_prompt,
                        "is_final_turn_in_input": False,
                        "sendable_to_other_user": True,  # placeholder - not everything will be, eg. tool call metadata
                    }
                )
                previous_turn = copy.deepcopy(current_turn)
                previous_role = current_role

            # if this is the last entry
            if ix == len(input_list[offset:]) - 1:
                # add previous, which will include current
                if len(previous_turn) > 0:
                    parsed_input.append(
                        {
                            "role": "user" if previous_role == "user" else "assistant",
                            "turn": previous_turn,
                            "tool_used": (
                                True
                                if any(["tool" in i["role"] for i in previous_turn])
                                else False
                            ),
                            "system_prompt": system_prompt,
                            "is_final_turn_in_input": True,
                            "sendable_to_other_user": True,
                        }
                    )

        total_length = 0
        for entry in parsed_input:
            total_length += len(entry["turn"])

        assert total_length == len(
            [i for i in input_list if not i["role"] == "system"]
        ), "Coder, you messed up your parsing in DatasetRow.get_turns()"

        assert parsed_input[-1]["is_final_turn_in_input"] is True

        return parsed_input

    def get_ideals(self):
        return json.loads(self.ideals)
