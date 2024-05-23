import textstat
import math
import openai
import os

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
        
        :param turn: a single conversational turn as a string
            CAUTION: You should keep the param name as "turn" 
        :return: You can return an integer (e.g., 2), \
                a floating point number (e.g., 2.8), \
                or a dictionary of metric/value pairs (e.g. {'metric1':value1, 'metric2':value2})
    """
    pass 

# A function template to process an entire conversation
def process_conversation(conversation:list)-> Union[int, float, Dict[str, int|float], List[Dict[str, int|float]]]:
    """
        Process an entire conversation and return the desired output
        
        :param conversation: an entire conversation as a list
            CAUTION: You should keep the param name as "conversation" 
        :return: You can return an integer, e.g., 2 \
                a floating point number, e.g., 2.8 \
                a dictionary of metric/value pairs, e.g. {'metric1':value1, 'metric2':value2}\
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
