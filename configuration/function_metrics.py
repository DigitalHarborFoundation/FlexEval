import textstat
import openai
import os
import re
import json
from typing import Union

##TODO - make a bunch of good examples of this
## and some bad ones...


def is_role(turn: list, role: str) -> dict:
    return {role: len([i for i in turn if i["role"] == role])}


def count_tool_calls(turn: list) -> list:
    """
    Calculate the number of calls to a tool, aggregated by name, in the turn.

    Elements of 'turn' look like one of two things:
    {
        "role": "user"
        "content": "some content"
    }
    OR
    {
        "role": "tool"
        "name":"name of tool"
        "content": [list of tool call info]
    }
    Args:
        conversation list: A list of dictionaries representing conversational turns.
                                             Each dictionary should have a 'role' key indicating the role of the participant.

    Returns:
        list: The number of conversational turns in the conversation, as a list of dicts with name/value keys
    """
    # Count number of tool calls by name
    counter = {}
    for entry in turn:
        if entry["role"] == "tool":
            counter[entry["name"]] = counter.get(entry["name"], 0) + 1

    # Convert to list of dictionaries for output
    results = []
    for name, val in counter.items():
        results.append({"name": name, "value": val})
    return results


def value_counts_by_tool_name(turn: list, json_key: str) -> list:
    """
    Counts the occurrences of particular values in the text content of tool call in the conversation.
    Assumes the roll will be tool, and that kwargs contains the argument json_key. values associated with
    that json_key for a specific tool name are separately aggregated with counts.

    Args:
        conversation (List[Dict[str, Any]]): A list of dictionaries representing conversational turns.
                                             Each dictionary should have a 'role' key indicating the role of the participant.
        json_key:  string that represents the key to look for in the content
                       of the tool call text

    Returns:
        list of name/value pairs for each parameter and function name combo
    """

    # Count number of tool calls by name
    counter = {}
    for entry in turn:
        if entry["role"] == "tool":
            # Find the text content
            for content_dict in entry["content"]:
                if content_dict["type"] == "text":
                    json_content_list = json.loads(content_dict["text"])
                    for json_dict in json_content_list:
                        if json_key in json_dict:
                            key = entry["name"] + "_" + json_dict[json_key]
                            counter[key] = counter.get(key, 0) + 1

    # Convert to list of dictionaries for output
    results = []
    for name, val in counter.items():
        results.append({"name": name, "value": val})
    return results


def count_role_entries_in_turn(
    turn: list,
) -> list:
    """
    Calculate the number of conversational turns for each role. Excludes the system prompt.

    Args:
        conversation (List[Dict[str, Any]]): A list of dictionaries representing conversational turns.
                                             Each dictionary should have a 'role' key indicating the role of the participant.

    Returns:
        List[Dict[str, Any]]: A list of dicts with role/value entries indicating the number of turns for each role
    """
    roles = set([i["role"] for i in turn])
    results = []
    for role in roles:
        # get just the turns for the role
        turns = [i for i in turn if i["role"] == role]
        # get the number of turns
        results.append({"name": role, "value": len(turns)})
    return results


# def number_of_entries(turn: List[Dict[str, Any]]) -> int:
#     """
#     Calculate the number of entries in each turn.

#     Args:
#         conversation (List[Dict[str, Any]]): A list of dictionaries representing conversational entries/turns.
#                                              Each dictionary should have a 'role' key indicating the role of the participant.

#     Returns:
#         int: The number of conversational turns in the conversation.
#     """
#     return len(turn)


def count_emojis(turn: str) -> Union[int, float]:
    """
    Calculate the number of emojis in a given text string.

    Args:
        turn (str): The input text string to be evaluated.

    Returns:
        Union[int, float]: The number of emojis in the input text.
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return len(emoji_pattern.findall(turn))


# def count_unusual_function_calls(turn: str) -> Union[int, float]:
#     """
#     See how often an exponential function is called with strange parameters


#     Args:
#         turn (str): The input text string to be evaluated.

#     Returns:
#         Union[int, float]: The number of emojis in the input text.
#     """
#     emoji_pattern = re.compile(
#         "["
#         "\U0001F600-\U0001F64F"  # emoticons
#         "\U0001F300-\U0001F5FF"  # symbols & pictographs
#         "\U0001F680-\U0001F6FF"  # transport & map symbols
#         "\U0001F1E0-\U0001F1FF"  # flags (iOS)
#         "\U00002702-\U000027B0"  # Dingbats
#         "\U000024C2-\U0001F251"
#         "]+",
#         flags=re.UNICODE,
#     )
#     return len(emoji_pattern.findall(turn))


def string_length(turn: str) -> int:
    """
    Calculate the length of the input string.

    Args:
        turn (str): The input text string whose length is to be measured.

    Returns:
        Union[int, float]: The length of the input string as an integer or float.
    """
    if turn is None:
        return 0
    return len(turn)


def flesch_reading_ease(turn: str) -> float:
    """
    Calculate the Flesch Reading Ease score for a given text string.

    The Flesch Reading Ease score is a readability test designed to indicate how difficult a passage
    in English is to understand. Higher scores indicate material that is easier to read; lower scores
    indicate material that is more difficult to read.

    Args:
        turn (str): The input text string to be evaluated.

    Returns:
        float: The Flesch Reading Ease score of the input text.
    """
    return textstat.flesch_reading_ease(turn)


def flesch_kincaid_grade(turn: str) -> float:
    """
    Calculate the Flesch-Kincaid Grade Level score for a given text string.

    The Flesch-Kincaid Grade Level score is a readability test designed to indicate the U.S. school
    grade level of the text. Higher scores indicate material that is more difficult to read and understand,
    suitable for higher grade levels.

    Args:
        turn (str): The input text string to be evaluated.

    Returns:
        float: The Flesch-Kincaid Grade Level score of the input text.
    """
    return textstat.flesch_kincaid_grade(turn)


def openai_moderation_api(turn: str, **kwargs) -> dict:
    """
    Calls the OpenAI Moderation API to analyze the given conversational turn for content moderation.
    Since the input is a string, it'll concatenate all the "content" together and pass it in

    Args:
        turn (str): The conversational turn to be analyzed.
        **kwargs (Any): Ignored for now

    Returns:
        Dict[str, float]: A dictionary of category scores from the moderation API response.
    """
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.moderations.create(input=turn)
    return response.results[0].model_dump(exclude_unset=True)["category_scores"]


def function_has_error(turn: list) -> int:
    """Returns the number of rendering errors if the turn is a function call
    or None otherwise
    """
    if turn.get("role", None) == "tool":
        ct = 0
        for element in turn.get("content", []):
            if "error" in element.get("type", ""):
                try:
                    errors = json.loads(element.get("text", "[]"))
                    ct += len(errors)
                except:
                    pass
        return ct
    else:
        return None
