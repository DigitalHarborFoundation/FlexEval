import textstat
import math
import openai
import os
import re
## ~.~ function templates starts ~.~
from typing import Union, Dict, List

# Example input: either a single turn as a string or an entire conversation as a list of libraries. 
turn_example = "This is a conversatioal turn."
conversation_example = [{'role':"X1", 'content': "Y1"}, 
                        {'role':"X2", 'content': "Y2"}, ...]

# A function template to process a single turn
def process_single_turn(turn: str) -> Union[int, float, Dict[str, int|float]]:
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
def process_conversation(conversation:list)-> Union[int, float, Dict[str, int|float], List[Dict[str, int|float]]]:
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

## ~.~ function templates ends ~.~


def string_length(sample):
    """Input is a text string.
    Output is a metric defined on that string.
    """
    return len(sample)


def flesch_reading_ease(sample):
    """Input is a text string.
    Output is a metric defined on that string.
    """
    return textstat.flesch_reading_ease(sample)


def flesch_kincaid_grade(sample):
    """Input is a text string.
    Output is a metric defined on that string.
    """
    return textstat.flesch_kincaid_grade(sample)


def terrysfunction(sample):
    x = sample * 2
    y = math.sqrt(sample)
    return x * y


def openai_moderation_api(sample, **kwargs):
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.moderations.create(input=sample)
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
    
        
        
    

