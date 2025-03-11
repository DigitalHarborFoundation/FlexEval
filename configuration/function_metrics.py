import textstat
import openai
import os
import re
import json
from typing import Union
import datetime

from flexeval.classes.Turn import Turn
from flexeval.classes.Message import Message
from flexeval.classes.Thread import Thread
from flexeval.classes.ToolCall import ToolCall


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
conversation_example = [
    {"role": "X1", "content": "Y1"},
    {"role": "X2", "content": "Y2"},
    ...,
]


# A function template to process a single message
def process_single_message(
    message: str,
) -> Union[int, float, dict[str, Union[int, float]]]:
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
def process_conversation(
    conversation: list,
) -> Union[
    int, float, dict[str, Union[int, float]], list[dict[str, Union[int, float]]]
]:
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
    """
    Return 1 is the role for this Turn or Message matches the passed in role,
    and 0 otherwise.

    Args:
    object: the Turn or Message
    role: a string with the desired role to check against
    """
    return {role: int(object.role == role)}


def is_langgraph_type(object: Union[Message], type: str) -> dict:
    """
    Return 1 is the langgraph type for this Message matches the passed in type,
    and 0 otherwise.

    Args:
    object: the Message
    type: a string with the desired type to check against
    """
    return {type: int(object.langgraph_type == type)}


def value_counts_by_tool_name(turn: list, json_key: str) -> dict:
    """
    Counts the occurrences of particular values in the text content of tool call in the conversation.
    Assumes the role will be tool, and that kwargs contains the argument json_key. values associated with
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


def message_matches_regex(message: Message, expression: str) -> dict:
    """Determines whether a message matches a regular expression specified by the user

    Outputs the number of matches detected using Pattern.findall()
    """

    # Compile the regular expression R
    pattern = re.compile(expression)

    # Use the fullmatch method to check if the entire string X matches the pattern
    match = pattern.findall(message.content)

    if match:
        return {expression: len(match)}
    else:
        return {expression: 0}


def count_of_parts_matching_regex(
    object: Union[Thread, Turn, Message], expression: str
) -> int:
    """Determines the total number of messages in this object
     matching a regular expression specified by the user. Ignores tool calls in object.

    Outputs the sum of the number of matches detected using Pattern.findall() across
    all entries in the object.
    """
    total_matches = {expression: 0}
    if isinstance(object, (Thread, Turn)):
        messages_to_match = object.messages
    else:
        messages_to_match = [object]

    for message in messages_to_match:
        total_matches[expression] += message_matches_regex(message, expression)[
            expression
        ]

    return total_matches


def tool_was_called(object: Union[Thread, Turn, Message]) -> float:
    """Returns 1 if a tool was called, and 0 otherwise"""
    for tc in object.toolcalls:
        return 1
    return 0


def count_tool_calls_by_name(object: Union[Thread, Turn, Message, ToolCall]) -> dict:
    """
    Counts how many times a ToolCall was used to call functions, with metric names
    equal to function names.

    NOTE: This function provides an example of how to go from higher levels of granularity
    (e.g., Thread) to lower levels of granularity (e.g., ToolCall).
    """
    # Extract ToolCall objects based on the type of object being passed in
    toolcalls = []
    if isinstance(object, (Thread, Turn)):
        for message in object.messages:
            toolcalls += [toolcall for toolcall in message.toolcalls]
    elif isinstance(object, Message):
        toolcalls += [toolcall for toolcall in object.toolcalls]
    else:  # Must be just a tool call
        toolcalls.append(object)

    # Count the toolcalls
    toolcall_counts = {}
    for toolcall in toolcalls:
        if toolcall.function_name not in toolcall_counts:
            toolcall_counts[toolcall.function_name] = 0
        toolcall_counts[toolcall.function_name] = (
            toolcall_counts[toolcall.function_name] + 1
        )

    return toolcall_counts


def count_numeric_tool_call_params_by_name(toolcall: ToolCall) -> list:
    """
    Extracts the values of all numeric ToolCall parameter inputs, with
    metric_name being the name of the corresponding parameter.
    """
    results = []
    toolcall_args = json.loads(toolcall.args)
    for arg_name, arg_value in toolcall_args.items():
        try:
            numeric_val = float(arg_value)
            # key = toolcall.function_name + "_" + arg_name
            results.append({"name": arg_name, "value": numeric_val})
        except:
            pass

    return results


def count_llm_models(thread: Thread) -> dict:
    """Provides a count of messages in the thread produced by each LLM model.
    Useful for quantifying which LLM generated the results - and agents can have more than 1 type.
    """
    results = {}
    for message in thread.messages:
        if message.model_name is not None:
            results[message.model_name] = results.get(message.model_name, 0) + 1
    return results


def count_tool_calls(object: Union[Thread, Turn, Message]) -> dict:
    """
    Provides a count of how many total tools calls there are in this Thread/Turn/Message.
    Differs from count_tool_calls_by_name because it does not return the names of the tool calls.
    """
    # Extract ToolCall objects based on the type of object being passed in
    toolcalls = []
    if isinstance(object, (Thread, Turn)):
        for message in object.messages:
            toolcalls += [toolcall for toolcall in message.toolcalls]
    else:  # must be a Message
        toolcalls += [toolcall for toolcall in object.toolcalls]
    return len(toolcalls)


# def count_tool_calls_by_name(object: Union[Thread, Turn, Message, ToolCall]) -> list:
#     # Extract ToolCall objects based on the type of object being passed in
#     toolcalls = []
#     if isinstance(object, (Thread, Turn)):
#         for message in object.messages:
#             toolcalls += [toolcall for toolcall in message.toolcalls]
#     elif isinstance(object, Message):
#         toolcalls += [toolcall for toolcall in object.toolcalls]
#     else:  # Must be just a tool call
#         toolcalls.append(object)

#     # Count the toolcalls
#     toolcall_counts = {}
#     for toolcall in toolcalls:
#         if toolcall.function_name not in toolcall_counts:
#             toolcall_counts[toolcall.function_name] = 0
#         toolcall_counts[toolcall.function_name] = (
#             toolcall_counts[toolcall.function_name] + 1
#         )

#     # Convert to a list of name: value dictionaries
#     results = []
#     for toolcall_name, toolcall_count in toolcall_counts.items():
#         results.append({"name": toolcall_name, "value": toolcall_count})
#     return results


def count_messages_per_role(
    object: Union[Thread, Turn], use_langgraph_roles=False
) -> list:
    """
    Calculate the number of conversational messages for each role. Excludes the system prompt.
    A message is counted even if the content for that action was blank (e.g., a blank message
    associated with a tool call).

    Args:
        Turn or Thread

    Returns:
        dict: A dictionary with roles as keys roles and values as counts of messages
    """
    results = {}
    for message in object.messages:
        if use_langgraph_roles:
            role = message.langgraph_type
        else:
            role = message.role
        results[role] = results.get(role, 0) + 1
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
    max_turn_id = (
        Turn.select(fn.max(Turn.id)).where(Turn.thread_id == turn.thread.id).scalar()
    )
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
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "\U00002702-\U000027b0"  # Dingbats
        "\U000024c2-\U0001f251"
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
    else:  # list
        # Sum up the lengths of the individual contents
        for role_content_dict in content:
            length += len(role_content_dict.get("content", ""))

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


def count_errors(object: Union[Thread, Turn, Message, ToolCall]) -> dict:
    """If a Thread, counts the errors of each type in the thread.
    If a Turn, Message, or ToolCall, ditto.

    It does this by iterating through ToolCalls and identifying whether there are
    entries like "*_errors" in tool_call.additional_kwargs

    If a ToolCall, returns 1 if there is an error of each type
    {
        "python_errors": 3,
        "javascript_errors": 1
    }
    """
    x = 1

    if isinstance(object, ToolCall):
        return {
            i: 1
            for i in json.loads(object.additional_kwargs)
            if (
                i.endswith("_errors")
                and json.loads(object.additional_kwargs)[i] is not None
            )
        }
    else:
        results = {}
        for toolcall in object.toolcalls:
            keys = [
                i
                for i in json.loads(toolcall.additional_kwargs)
                if i.endswith("_errors")
            ]
            for key in keys:
                if json.loads(toolcall.additional_kwargs).get(key, None) is not None:
                    results[key] = results.get(key, 0) + 1
        return results


def count_tokens(object: Union[Thread, Turn, Message]) -> dict:
    """
    Counts how many prompt_tokens and completion_tokens tokens are used.

    These values are record at the Message level, so this function sums over messages
    if the input type is Thread or Turn
    """
    # Extract ToolCall objects based on the type of object being passed in
    prompt_tokens = 0
    completion_tokens = 0
    if isinstance(object, (Thread, Turn)):
        for message in object.messages:
            if message.prompt_tokens is not None:
                prompt_tokens += message.prompt_tokens
            if message.completion_tokens is not None:
                completion_tokens += message.completion_tokens
    elif isinstance(object, Message):
        if object.prompt_tokens is not None:
            prompt_tokens += object.prompt_tokens
        if object.completion_tokens is not None:
            completion_tokens += object.completion_tokens

    return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


def latency(object: Union[Thread, Turn, Message]) -> float:
    """
    Returns the estimated time, in seconds, that it took for the Turead/Turn/Message to be generated, in seconds.

    For Turns and Messages, this is done by comparing the timestamp of the Turn/Message, which indicates the
    output time of that Turn/Message - to the timestamp fo the previous Turn/Message.
    For example, if a Message is generated at 1:27.3 but the previous message was generated at 1:23.1, the latency was 4.2 seconds.

    For Threads, the latenecy is calculated as the time difference, again in seconds, between the first and last message.

    """
    if isinstance(object, Thread):
        # difference between earliest and latest message
        first_message_ts = object.messages.order_by(Message.langgraph_ts)[
            0
        ].langgraph_ts
        final_message_ts = object.messages.order_by(Message.langgraph_ts.desc())[
            0
        ].langgraph_ts
        first_datetime = datetime.datetime.fromisoformat(first_message_ts)
        final_datetime = datetime.datetime.fromisoformat(final_message_ts)
        difference = final_datetime - first_datetime
        latency = difference.total_seconds()
    elif isinstance(object, (Message)):
        # difference between this message and the one right before it in the thread
        # easy way to do this is to take the time difference between this the closest
        # message just before this one
        # If there is NO messge right before it, return None - there is no way to know the latency
        my_datetime = object.langgraph_ts
        # message in the same thread, earlier than this one, and pick the last langgraph_ts in that list
        message_just_before_this_one = (
            Message.select()
            .where(Message.thread == object.thread, Message.langgraph_ts < my_datetime)
            .order_by(Message.langgraph_ts.desc())
            .first()
        )
        if message_just_before_this_one is None:
            latency = 0.0
        else:
            difference = datetime.datetime.fromisoformat(
                my_datetime
            ) - datetime.datetime.fromisoformat(
                message_just_before_this_one.langgraph_ts
            )
            latency = difference.total_seconds()

    elif isinstance(object, Turn):
        # if it's a thread,
        # you want the difference between the LAST message in the turn
        # and the LAST message in the previous turn
        # or equivalently, the closest previous timestamp from any turn other than yours

        # get timestamp of last message associated with this Turn
        my_datetime = (
            Message.select()
            .where(Message.turn == object)
            .order_by(Message.langgraph_ts.desc())
            .first()
        ).langgraph_ts
        # Then get the mmessage in the same Thread
        # with a timestamp just before this one
        message_just_before_this_one = (
            Message.select()
            .where(
                Message.thread == object.thread,
                Message.langgraph_ts < my_datetime,
            )
            .order_by(Message.langgraph_ts.desc())
            .first()
        )
        if message_just_before_this_one is None:
            latency = 0.0
        else:
            difference = datetime.datetime.fromisoformat(
                my_datetime
            ) - datetime.datetime.fromisoformat(
                message_just_before_this_one.langgraph_ts
            )
            latency = difference.total_seconds()

    return latency
