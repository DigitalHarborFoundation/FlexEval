import textstat
import openai
import os
import re
import json
from typing import Union

from classes.Turn import Turn
from classes.Message import Message
from classes.Thread import Thread
from classes.ToolCall import ToolCall


## ~.~ function templates starts ~.~
from typing import Union

# Example input types:
# - a single message as a string
# - an entire conversation (i.e., Thread) as a list of dictionaries
# - an object of type Thread, Turn, Message, or ToolCall.
#   These objects have the same fields as in the correspondingly
#   named databases, and can access objects at higher or lower
#   levels of granularity. Examples are provided below for working 
#   with these objects.
turn_example = "This is a conversational turn."
conversation_example = [{'role':"X1", 'content': "Y1"}, 
                        {'role':"X2", 'content': "Y2"}, ...]

# A function template to process a single message
def process_single_message(message: str) -> Union[int, float, dict[str, Union[int, float]]]:
    """
        Process a single conversational message and return the desired output
        
        Args: 
        message (str): a single conversational message as a string
                NOTE: Metrics that take a string as input are valid at the Turn
                      and Message levels.
        
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
                NOTE: Metrics that take a list as input are valid at the Thread
                      and Turn levels.
        Returns: 
        an integer, e.g., 2 \
        or a floating point number, e.g., 2.8 \
        or a dictionary of metric/value pairs, e.g. {'metric1':value1, 'metric2':value2}\
        or a list of dictionaries. The key can be either 'role' or 'metric'. \
            e.g., [{"role":role1, "value":value1}, {"role":role2, "value":value2}, ...]
    """
    pass 

def is_role(object: Union[Turn, Message], role: str) -> dict:
    '''
    Return 1 is the role for this Turn or Message matches the passed in role,
    and 0 otherwise.

    Args:
    object: the Turn or Message
    role: a string with the desired role to check against
    '''
    return {role: int(object.role == role)}



def value_counts_by_tool_name(turn: list, json_key: str) -> dict:
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

    return counter


def count_tool_calls_by_name(object: Union[Thread, Turn, Message, ToolCall]) -> dict:
    '''
    Counts how many times a ToolCall was used to call functions, with metric names
    equal to function names. 

    NOTE: This function provides an example of how to go from higher levels of granularity
    (e.g., Thread) to lower levels of granularity (e.g., ToolCall).
    '''
    # Extract ToolCall objects based on the type of object being passed in
    toolcalls = []
    if isinstance(object, (Thread, Turn)):
        for message in object.messages:
            toolcalls += [toolcall for toolcall in message.toolcalls]
    elif isinstance(object, Message):
        toolcalls += [toolcall for toolcall in object.toolcalls]
    else: # Must be just a tool call
        toolcalls.append(object)
    
    # Count the toolcalls
    toolcall_counts = {}
    for toolcall in toolcalls:
        if toolcall.function_name not in toolcall_counts:
            toolcall_counts[toolcall.function_name] = 0
        toolcall_counts[toolcall.function_name] = toolcall_counts[toolcall.function_name] + 1

    return toolcall_counts

def count_numeric_tool_call_params_by_name(toolcall: ToolCall) -> list:
    '''
    Extracts the values of all numeric ToolCall parameter inputs, with
    metric_name being the name of the corresponding parameter.
    '''
    results = []
    toolcall_args = json.loads(toolcall.args)
    for arg_name, arg_value in toolcall_args.items():
        try:
            numeric_val = float(arg_value)
            key = toolcall.function_name + "_" + arg_name
            results.append({"name": key, "value": numeric_val})
        except:
            pass

    return results

def count_role_entries(
    turn_or_thread: list,
) -> list:
    """
    Calculate the number of conversational actions for each role. Excludes the system prompt.
    An action is counted even if the content for that action was blank (e.g., a blank message
    associated with a tool call).

    Args:
        turn_or_thread (list): List of dictionaries with the role and content from each 
                                message in the turn or thread.

    Returns:
        List[Dict[str, Any]]: A list of dicts with role/value entries indicating the number of turns for each role
    """
    roles = set([i["role"] for i in turn_or_thread])
    results = []
    for role in roles:
        # get just the turns for the role
        turns = [i for i in turn_or_thread if i["role"] == role]
        # get the number of turns
        results.append({"name": role, "value": len(turns)})
    return results

def is_last_turn_in_thread(turn: Turn) -> int:
    """
    Returns 1 if this turn is the final turn in its thread, and 0 otherwise.

    Args:
        turn: turn to evaluate
    
    Returns:
        int: 1 for this being the temporally last turn in the thread, 0 otherwise
    """
    from peewee import fn
    # Select the id of the Turn in the current thread that has the max value
    max_turn_id = Turn.select(fn.max(Turn.id)).where(Turn.thread_id == turn.thread.id).scalar()
    return int(max_turn_id == turn.id)


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

def string_length(object: Union[Thread, Turn, Message]) -> int:
    """
    Calculate the length of the content.

    Args:
        object (Union[Thread, Turn, Message]): 

    Returns:
        int: The length of the content of the messages (added together for
            thread and turn that may contain more than one message)
    """
    content = object.get_content()
    length = 0
    if isinstance(content, str):
        length = len(content)
    else: # list
        # Sum up the lengths of the individual contents
        for role_content_dict in content:
            length += len(role_content_dict.get('content', ''))

    return length


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
        