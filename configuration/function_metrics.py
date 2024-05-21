import textstat
import math
import openai
import os


# Desired thing - want to be able to pass in function name as parameter
#


def number_of_turns(conversation):
    """Input is a list of conversational turns.
    Output is a dictionary of metrics -- by role.
    """
    roles = set([i["role"] for i in conversation])
    results = {}
    for role in roles:
        # get just the turns for the role
        turns = [i for i in conversation if i["role"] == role]
        # get the number of turns
        results[role] = len(turns)
    return results


def string_length(sample):
    """Input is a text string.
    Output is a metric defined on that string.
    """
    if sample is None:
        return 0
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
