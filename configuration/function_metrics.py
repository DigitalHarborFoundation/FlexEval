import textstat
import openai
import os
import re
import json
from typing import List, Dict, Any, Union

# A metric is a function that
# - accepts a conversation or conversational turn as input
# - produces a number or dictionary of numbers as output

# If your metric accepts a LIST as input, we'll assume it's per-conversation
#


def number_of_turns_per_role(conversation: List[Dict[str, Any]], **kwargs:Any) -> Dict[int, float]:
    """
    Calculate the number of conversational turns for each role. Excludes the system prompt.

    Args:
        conversation (List[Dict[str, Any]]): A list of dictionaries representing conversational turns.
                                             Each dictionary should have a 'role' key indicating the role of the participant.

    Returns:
        List[Dict[str, Any]]: A list of dicts with role/value entries indicating the number of turns for each role
    """
    roles = set([i["role"] for i in conversation])
    results = []
    for role in roles:
        # get just the turns for the role
        turns = [i for i in conversation if i["role"] == role]
        # get the number of turns
        results.append({"role": role, "value": len(turns)})
    return results


def number_of_turns(conversation: List[Dict[str, Any]], **kwargs: Any) -> int:
    """
    Calculate the number of conversational turns in the conversation. Excludes the system prompt.

    Args:
        conversation (List[Dict[str, Any]]): A list of dictionaries representing conversational turns.
                                             Each dictionary should have a 'role' key indicating the role of the participant.

    Returns:
        int: The number of conversational turns in the conversation.
    """
    turns = set([i["role"] for i in conversation if i["role"] not in ["system"]])
    return len(turns)


def number_of_tool_calls(conversation: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
    """
    Calculate the number of calls to a tool, aggregated by name, in the conversation. Assumes the roll will be tool.

    Args:
        conversation (List[Dict[str, Any]]): A list of dictionaries representing conversational turns.
                                             Each dictionary should have a 'role' key indicating the role of the participant.

    Returns:
        int: The number of conversational turns in the conversation.
    """
    # Count number of tool calls by name
    counter = {}
    for turn in conversation:
        if turn["role"] == "tool":
            counter[turn["name"]] = counter.get(turn["name"], 0) + 1
    
    # Convert to list of dictionaries for output
    results = []
    for name, val in counter.items():
        results.append({"role": name, "value": val})
    return results


def value_counts_by_tool_name(conversation: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
    """
    Counts the occurrences of particular values in the text content of tool call in the conversation. 
    Assumes the roll will be tool, and that kwargs contains the argument json_key. values associated with
    that json_key for a specific tool name are separately aggregated with counts.

    Args:
        conversation (List[Dict[str, Any]]): A list of dictionaries representing conversational turns.
                                             Each dictionary should have a 'role' key indicating the role of the participant.
        **kwargs: Any: keyword args must contain json_key, a string that represents the key to look for in the content
                       of the tool call text

    Returns:
        int: The number of conversational turns in the conversation.
    """
    # Look for keyword arg indicating what json we're looking for
    json_key = kwargs["json_key"]

    # Count number of tool calls by name
    counter = {}
    for turn in conversation:
        if turn["role"] == "tool":
            # Find the text content
            for content_dict in turn["content"]:
                if content_dict["type"] == "text":
                    json_content_list = json.loads(content_dict["text"])
                    for json_dict in json_content_list:
                        if json_key in json_dict:
                            key = turn["name"] + "_" + json_dict[json_key]
                            counter[key] = counter.get(key, 0) + 1
            
    # Convert to list of dictionaries for output
    results = []
    for name, val in counter.items():
        results.append({"role": name, "value": val})
    return results

def count_emojis(turn: str, **kwargs:Any) -> Union[int, float]:
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


def string_length(turn: str, **kwargs: Any) -> Union[int, float]:
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


def flesch_reading_ease(turn: str, **kwargs:Any) -> Union[int, float]:
    """
    Calculate the Flesch Reading Ease score for a given text string.

    The Flesch Reading Ease score is a readability test designed to indicate how difficult a passage
    in English is to understand. Higher scores indicate material that is easier to read; lower scores
    indicate material that is more difficult to read.

    Args:
        turn (str): The input text string to be evaluated.

    Returns:
        Union[int, float]: The Flesch Reading Ease score of the input text.
    """
    return textstat.flesch_reading_ease(turn)


def flesch_kincaid_grade(turn: str, **kwargs:Any) -> Union[int, float]:
    """
    Calculate the Flesch-Kincaid Grade Level score for a given text string.

    The Flesch-Kincaid Grade Level score is a readability test designed to indicate the U.S. school
    grade level of the text. Higher scores indicate material that is more difficult to read and understand,
    suitable for higher grade levels.

    Args:
        turn (str): The input text string to be evaluated.

    Returns:
        Union[int, float]: The Flesch-Kincaid Grade Level score of the input text.
    """
    return textstat.flesch_kincaid_grade(turn)


def openai_moderation_api(turn: str, **kwargs: Any) -> Dict[str, float]:
    """
    Calls the OpenAI Moderation API to analyze the given conversational turn for content moderation.

    Args:
        turn (str): The conversational turn to be analyzed.
        **kwargs (Any): Ignored for now

    Returns:
        Dict[str, float]: A dictionary of category scores from the moderation API response.
    """
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.moderations.create(input=turn)
    return response.results[0].model_dump(exclude_unset=True)["category_scores"]
