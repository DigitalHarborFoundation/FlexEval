from pydantic import BaseModel, Field, field_validator


class Rubric(BaseModel):
    prompt: str = Field(description="Prompt for the rubric.")
    choice_scores: dict[str, int | float] = Field(
        default_factory=dict, description="Choices."
    )
    name: str | None = Field(None, description="Optional name of the rubric.")
    notes: str | None = Field(None, description="Optional notes.")

    @field_validator("prompt")
    @classmethod
    def is_rubric_prompt_valid(cls, prompt: str):
        if "{conversation}" in prompt and "{context}" in prompt:
            raise ValueError(
                "Your rubric should not have both {conversation} and {context}. Please check the README file for more information about how to write FlexEval rubrics."
            )

        if "{completion}" in prompt and "{content}" in prompt:
            raise ValueError(
                "Your rubric should not have both {content} and {completion}. Please check the README file for more information about how to write FlexEval rubrics."
            )
        return prompt

    @field_validator("choice_scores")
    @classmethod
    def check_non_empty(cls, v):
        if not v:
            raise ValueError("Must provide at least two choice scores.")
        return v


class RubricsCollection(BaseModel):
    """Collection of rubrics that can be used as :class:`~flexeval.schema.eval_schema.RubricItem` s."""

    rubrics: dict[str, Rubric] = Field(
        default_factory=dict,
        description="Mapping of rubric names to Rubrics. The rubric names are used for matching metrics to specific rubrics.",
    )
