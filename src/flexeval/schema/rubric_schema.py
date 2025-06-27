from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator


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

    @field_validator("choice_scores")
    @classmethod
    def check_non_empty(cls, v):
        if not v:
            raise ValueError("Must provide at least two choice scores.")
        return v


class RubricsCollection(BaseModel):
    rubrics: dict[str, Rubric] = Field(default_factory=dict, description="")
