import textstat
import math
import openai
import os

## ~~function templates starts~~
from typing import Union, Dict, List, Any

SingleTurnExample = "This is a conversatioal turn."
ConversationExample = [{'role':"X1", 'content': "Y1"}, 
                       {'role':"X2", 'content': "Y2"}, ...]

def process_single_turn(SingleTurnExample: str) -> Union[str, int, float, Dict[str, Any], List[Any]]:
    """
        Process a single conversational turn and return the desired output. 
        The output can be a string, integer, float, a dictionary, or a list. 
    """
    pass 

def process_conversation(ConversationExample:list)-> Union[str, int, float, Dict[str, Any], List[Any]]:
    """
        Process a single conversational turn and return the desired output. 
        The output can be a string, integer, float, a dictionary, or a list. 
    """
    pass 

## ~~function templates ends~~


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
