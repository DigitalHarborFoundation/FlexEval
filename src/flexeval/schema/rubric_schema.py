from typing import Annotated
from pydantic import AfterValidator, Field, BaseModel


def is_rubric_prompt_valid(prompt: str):
    if "{conversation}" in prompt and "{context}" in prompt:
        raise ValueError(
            "Your rubric should not have both {conversation} and {context}. Please check the README file for more information about how to write FlexEval rubrics."
        )

    if "{completion}" in prompt and "{content}" in prompt:
        raise ValueError(
            "Your rubric should not have both {content} and {completion}. Please check the README file for more information about how to write FlexEval rubrics."
        )
    return prompt


class Rubric(BaseModel):
    prompt: Annotated[str, AfterValidator(is_rubric_prompt_valid)] = Field(
        description="Prompt for the rubric."
    )
    choice_scores: dict[str, int | float] = Field(
        default_factory=dict, description="Choices."
    )
    name: str | None = Field(None, description="Optional name of the rubric.")
    notes: str | None = Field(None, description="Optional notes.")


class RubricsCollection(BaseModel):
    rubrics: dict[str, Rubric] = Field(default_factory=dict, description="")
