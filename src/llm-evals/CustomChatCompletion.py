from typing import Any, Union
from evals.api import CompletionResult
from evals.base import CompletionFnSpec
from evals.prompt.base import (
    ChatCompletionPrompt,
    OpenAICreateChatPrompt,
    Prompt,
)
from evals.record import record_sampling

from configuration.completion_functions import *


def print_kwargs(kw):
    results = {}
    for key, value in kw.items():
        try:
            results[str(key)] = str(value)
        except AttributeError as e:
            print(f"Error printing {key}: {e}")
    return str(results)


class CustomChatCompletionResult(CompletionResult):
    def __init__(self, raw_data: Any, prompt: Any):
        self.raw_data = raw_data
        self.prompt = prompt

    def get_completions(self) -> list[str]:
        # iterates through all messages (1 or more) in the
        # completion and adds those strings to a list
        completions = []
        if self.raw_data and "choices" in self.raw_data:
            for choice in self.raw_data["choices"]:
                if "message" in choice:
                    completions.append(choice["message"]["content"])
        return completions


class CustomChatCompletionFn(CompletionFnSpec):
    def __str__(self):
        return str(self.completion_fn_name)

    def __init__(
        self,
        # Args from the yaml spec are passed in as kwargs
        *args,
        **kwargs,
    ):
        self.completion_function_kwargs = kwargs
        self.completion_fn_name = kwargs["function_name"]

    def __call__(
        self,
        prompt: Union[str, list[dict[str, str]]],
        *args,
        **kwargs,
    ) -> CustomChatCompletionResult:
        if isinstance(prompt, dict):
            prompt = prompt["input"]
        # Parse input -  make sure you can convert it to a 'Prompt' type
        if not isinstance(prompt, Prompt):
            assert (
                isinstance(prompt, str)
                or (
                    isinstance(prompt, list)
                    and all(isinstance(token, int) for token in prompt)
                )
                or (
                    isinstance(prompt, list)
                    and all(isinstance(token, str) for token in prompt)
                )
                or (
                    isinstance(prompt, list)
                    and all(isinstance(msg, dict) for msg in prompt)
                )
            ), f"Got type {type(prompt)}, with val {type(prompt[0])} for prompt, expected str or list[int] or list[str] or list[dict[str, str]]"
            prompt = ChatCompletionPrompt(
                raw_prompt=prompt,
            )

        # Converts from "Prompt" type back to List
        formatted_prompt: OpenAICreateChatPrompt = prompt.to_formatted_prompt()

        # Check if the function name exists in the global namespace and call it
        if self.completion_fn_name in globals() and callable(
            globals()[self.completion_fn_name]
        ):
            completion = globals()[self.completion_fn_name](
                conversation_history=formatted_prompt, **self.completion_function_kwargs
            )
        else:
            print(
                "In CustomChatCompletion.py: No callable function named "
                + self.completion_fn_name
                + " found."
            )
            completion = None
            # return self.metric_name, None

        # convert result to required format, a CompletionResult class
        result = CustomChatCompletionResult(prompt=prompt, raw_data=completion)
        record_sampling(prompt=result.prompt, sampled=result.get_completions())
        return result
