import textstat
import openai
import os
import re
from typing import List, Dict, Any, Union, AnyStr
import json

# A metric is a function that
# - accepts a conversation or conversational turn as input
# - produces a number or dictionary of numbers as output

# If your metric accepts a LIST as input, we'll assume it's per-conversation
#


def number_of_turns_per_role(conversation: List[Dict[str, Any]]) -> Dict[int, float]:
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


def number_of_turns(conversation: List[Dict[str, Any]]) -> int:
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


def count_unusual_function_calls(turn: str) -> Union[int, float]:
    """
    See how often an exponential function is called with strange parameters



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


def string_length(turn: str) -> Union[int, float]:
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


def flesch_reading_ease(turn: str) -> Union[int, float]:
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


def flesch_kincaid_grade(turn: str) -> Union[int, float]:
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


def function_has_error(turn: list):
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
