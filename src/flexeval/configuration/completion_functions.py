"""This file contains a list of Python functions that accept conversations as input
and produce conversational turns (aka completions) as output.

When writing a new function, the arguments must include, at minimum:
* conversation_history - list of dictionaries with keys ("role","content"), whose values are strings
* kwargs - dictionary of optional values that can probably be ignored
Other arguments can be added, but then must also be specified
in the "completion_llm" section of the evals.yaml config.

The outputs must conform to the structure described here:
https://platform.openai.com/docs/guides/text-generation/chat-completions-api
with the following format:
    completion = {
        "choices": [
            {
                "message":{
                    "content": MY_CONTENT_HERE,
                    "role":"assistant"
                }
            }
        ]
    }

"""

import json
import logging
import os
from typing import Any, Dict, List

import litellm
import requests
import tiktoken
from openai import OpenAI

logger = logging.getLogger(__name__)


def echo_completion(
    conversation_history: List[Dict[str, Any]],
    **kwargs: Any,
) -> Dict[str, Any]:
    prev_message = (
        conversation_history[0]["content"]
        if len(conversation_history) > 0
        else "No messages yet."
    )
    response = prev_message
    if "response" in kwargs:
        response = kwargs["response"]
    # estimate token usage using a default tokenizer
    tokenizer = tiktoken.get_encoding("cl100k_base")
    completion_tokens = len(tokenizer.encode(response))
    prompt_tokens = len(
        tokenizer.encode(
            "".join([message["content"] for message in conversation_history])
        )
    )
    completion = {
        "choices": [{"message": {"content": response, "role": "assistant"}}],
        "model": "echo",
        "usage": {
            "completion_tokens": completion_tokens,
            "prompt_tokens": prompt_tokens,
        },
    }
    return completion


def litellm_completion(
    conversation_history: list[dict[str, Any]],
    model: str,
    n: int = 1,
    **kwargs,
) -> dict[str, Any]:
    """
    Generate a completion for a given conversation history using LiteLLM's completion().

    Args:
        conversation_history (List[Dict[str, Any]]): The conversation history as a list of message dictionaries.
        model (str): The name of the model to use for the completion.
        n (int, optional): The number of completion choices to generate. Defaults to 1.
        **kwargs (Any): Additional keyword arguments to pass to completion(). Allowed values vary depending on the chosen model.

    Returns:
        Dict[str, Any]: The response.
    """
    response = litellm.completion(
        messages=conversation_history,
        model=model,
        n=n,
        **kwargs,
    )
    return response.model_dump(exclude_unset=True)


def open_ai_completion(
    conversation_history: List[Dict[str, Any]],
    model_name: str,
    api_key_name: str,
    n: int = 1,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Generate a completion for a given conversation history using OpenAI's chat completion API.

    Args:
        conversation_history (List[Dict[str, Any]]): The conversation history as a list of message dictionaries.
        model_name (str): The name of the OpenAI model to use for the completion.
        api_key_name (str): The environment variable name where the API key is stored.
        n (int, optional): The number of completion choices to generate. Defaults to 1.
        **kwargs (Any): Additional keyword arguments to pass to the OpenAI API client.

    Returns:
        Dict[str, Any]: The response from the OpenAI API with unset fields excluded.
    """
    client = OpenAI(api_key=os.getenv(api_key_name))

    raw_response = client.chat.completions.create(
        model=model_name, messages=conversation_history, n=int(n), **kwargs
    )

    return raw_response.model_dump(exclude_unset=True)


def open_ai_completion_async(
    conversation_history: List[Dict[str, Any]],
    model_name: str,
    api_key_name: str,
    n: int = 1,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Generate a completion for a given conversation history using OpenAI's chat completion API.

    Args:
        conversation_history (List[Dict[str, Any]]): The conversation history as a list of message dictionaries.
        model_name (str): The name of the OpenAI model to use for the completion.
        api_key_name (str): The environment variable name where the API key is stored.
        n (int, optional): The number of completion choices to generate. Defaults to 1.
        **kwargs (Any): Additional keyword arguments to pass to the OpenAI API client.

    Returns:
        Dict[str, Any]: The response from the OpenAI API with unset fields excluded.
    """
    client = OpenAI(api_key=os.getenv(api_key_name))

    raw_response = client.chat.completions.create(
        model=model_name, messages=conversation_history, n=int(n), **kwargs
    )

    return raw_response.model_dump(exclude_unset=True)


def jan_completion(conversation_history, model_name, endpoint, **kwargs):
    # Example: reuse your existing OpenAI setup

    client = OpenAI(base_url=endpoint, api_key="not-needed")
    raw_response = client.chat.completions.create(
        model=model_name, messages=conversation_history, temperature=0.7, **kwargs
    )
    return raw_response.model_dump(exclude_unset=True)


def lm_studio_completion(conversation_history, model_name, endpoint, **kwargs):
    # Example: reuse your existing OpenAI setup

    client = OpenAI(base_url=endpoint, api_key="not-needed")

    raw_response = client.chat.completions.create(
        model=model_name,
        messages=conversation_history,
        temperature=0.7,
    )
    return raw_response.model_dump(exclude_unset=True)


def generic_rest_api_completion(
    conversation_history,
    api_key_name: str,
    endpoint: str,
    **kwargs,
):
    auth_key = os.environ.get(api_key_name, None)

    # Headers including the authentication key and content type
    headers = {
        "Authorization": f"Bearer {auth_key}",
        "Content-Type": "application/json",
    }

    # Sending a POST request
    response = requests.post(
        endpoint, data=json.dumps(conversation_history), headers=headers
    )
    response_data = response.json()
    completion = response_data["completion"]
    # Check if the request was successful
    if response.status_code == 200:
        logger.info("Success:", response.text)
    else:
        logger.info("Error:", response.text)

    completion = {
        "choices": [{"message": {"content": completion, "role": "assistant"}}]
    }
    return completion


# when no completion function is needed
def no_completion_fn(
    conversation_history,
    **kwargs,
):
    completion = {
        "choices": [{"message": {"content": "hello world", "role": "assistant"}}]
    }
    return completion


def gpt_3p5_turbo(conversation_history, model_name, key_name, **kwargs):
    client = OpenAI(api_key=os.getenv(key_name))
    raw_response = client.chat.completions.create(
        model="gpt-3.5-turbo", messages=conversation_history
    )
    return raw_response.model_dump(exclude_unset=True)


def placeholder_completion(conversation_history, model_name, **kwargs):
    """This is just for testing -- always returns 'hi'"""
    return {"choices": [{"message": {"content": "hi", "role": "assistant"}}]}
