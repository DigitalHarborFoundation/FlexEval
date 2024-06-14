import textstat
import openai
import os
import re
from typing import List, Dict, Any, Union
import json


## ~.~ function templates starts ~.~
from typing import Union

# Example input: either a single turn as a string or an entire conversation as a list of libraries. 
turn_example = "This is a conversatioal turn."
conversation_example = [{'role':"X1", 'content': "Y1"}, 
                        {'role':"X2", 'content': "Y2"}, ...]

# A function template to process a single turn
def process_single_turn(turn: str) -> Union[int, float, dict[str, Union[int, float]]]:
    """
        Process a single conversational turn and return the desired output
        
        Args: 
        turn (str): a single conversational turn as a string
            CAUTION: You should keep the param name as "turn" 
        
        Returns:
        an integer (e.g., 2), \
        or a floating point number (e.g., 2.8), \
        or a dictionary of metric/value pairs (e.g. {'metric1':value1, 'metric2':value2})
    """
    pass 

# A function template to process an entire conversation
def process_conversation(conversation:list)-> Union[int, float, dict[str, Union[int, float]], list[dict[str, Union[int, float]]]]:
    """
        Process an entire conversation and return the desired output
        
        Args: 
        conversation (list): an entire conversation as a list
            CAUTION: You should keep the param name as "conversation" 
        
        Returns: 
        an integer, e.g., 2 \
        or a floating point number, e.g., 2.8 \
        or a dictionary of metric/value pairs, e.g. {'metric1':value1, 'metric2':value2}\
        or a list of dictionaries. The key can be either 'role' or 'metric'. \
            e.g., [{"role":role1, "value":value1}, {"role":role2, "value":value2}, ...]
    """
    pass 


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


def error_count(error_list:list) -> int:
    """
    Used in rendering_error_count function to identify and count any plot rendering errors
    
    Args:
        error_list (list): the list in the conversation containing plot rendering error information 

    Returns:
        int: a count number of the errors
    """
    error_count = 0
    for error_dict in error_list:
        for key, value in error_dict.items():
            if key == "text" and value != "[]" and len(value) > 2:
                error_count += 1
    return error_count


def rendering_error_count(conversation: list) -> dict:
    """
    Process a conversation to identify and count plot rendering errors if any
    
    Args: 
    conversation (list): an entire conversation as a list

    Returns:
    dict: {
            'expression_error_count': value,
            'javascript_log_error_count': value
        }
    """
    try:
        tool_call_list = [item for item in conversation if item.get("role") == "tool"]
        
        if not tool_call_list:
            expression_error_count = 0
            javascript_log_error_count = 0
        
        else: 
            # extract the values for the targeted errors
            for tool_call in tool_call_list:
                content =  tool_call["content"]
                expression_errors = [item for item in content if item.get("type") == "expression_errors"]
                javascript_log_errors = [item for item in content if item.get("type") == "javascript_log_errors"]
                # count the errors
                expression_error_count = error_count(expression_errors)
                javascript_log_error_count = error_count(javascript_log_errors)
        
        result = {
            'expression_error_count':expression_error_count,
            'javascript_log_error_count': javascript_log_error_count
        }
        
        return result
    
    except (KeyError, IndexError, TypeError, ValueError) as e:
        print(f"An error occurred: {e}")
        
        
def function_name_count(conversation:list) -> int:
    """
    Process a conversation to identify and count the number of instances where function names are revealed during a tool call 

    Args:
        conversation (list): an entire conversation as a list

    Returns:
        int: the count number of instances where function names are revealed
    """
    
    function_list = [
    "plot_other_diagram",
    "plot_one_or_more_equations_or_inequalities",
    "plot_line_with_slope_and_intercept",   
    "plot_line_with_coefficients",
    "plot_single_linear_inequality_with_slope_and_intercept",
    "plot_absolute_value_function",
    "plot_square_root_function",
    "plot_parabola_with_features_labeled",
    "plot_parabola_with_alternate_format",
    "plot_exponential_with_features_labeled", 
]
    function_name_count = 0
    
    try:

        assistant_turn = [item for item in conversation if item.get("role") == "assistant"]
        
        if not assistant_turn:
            function_name_count = 0
            
        else:
             for function in function_list:
                    pattern = r"function\." + re.escape(function)
                    for turn in assistant_turn:
                        content = turn.get("content")
                        if content:
                            function_name_count += len(re.findall(pattern, content))

        return function_name_count        

    except (KeyError, IndexError, TypeError, ValueError) as e:
        print(f"An error occurred: {e}")
    
        

