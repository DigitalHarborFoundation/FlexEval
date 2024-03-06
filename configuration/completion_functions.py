

# Each function must output a data structure described here:
# # https://platform.openai.com/docs/guides/text-generation/chat-completions-api
# completion = {
#     "choices": [
#         {
#             "message":{
#                 "content": MY_CONTENT_HERE,
#                 "role":"assistant"
#             }
#         }
#     ]
# }
# In addition,each function must have two inputs:
# 1 - conversation_history
# 2 - model_name


from openai import OpenAI
import os
import json
import requests


def jan_completion(conversation_history, model_name, endpoint, **kwargs):
    # Example: reuse your existing OpenAI setup

    client = OpenAI(base_url=endpoint, api_key="not-needed")

    raw_response = client.chat.completions.create(
        model=model_name,
        messages=conversation_history,
        temperature=0.7,
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


def open_ai_completion(conversation_history, model_name, api_key_name, **kwargs):
    client = OpenAI(api_key=os.getenv(api_key_name))
    raw_response = client.chat.completions.create(
        model=model_name,
        messages=conversation_history,
    )
    return raw_response.model_dump(exclude_unset=True)


def generic_rest_api_completion(
    conversation_history,
    model_name,
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
        print("Success:", response.text)
    else:
        print("Error:", response.text)

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
    # print(raw_response.model_dump_json(indent=2, exclude_unset=True))
    # print(raw_response.choices[0]['message']['content'])
    return raw_response.model_dump(exclude_unset=True)
