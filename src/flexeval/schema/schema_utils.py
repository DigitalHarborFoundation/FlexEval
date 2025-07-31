import types
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, PlainValidator


def validate_python_module(value: Any) -> Any:
    if not isinstance(value, types.ModuleType):
        raise ValueError(f"Expected a module, got a '{type(value)}'.")
    return value


ModuleType = Annotated[
    types.ModuleType,
    PlainValidator(validate_python_module),
    PlainSerializer(lambda x: str(x.__name__)),
]


def convert_none_or_empty_string_to_dict(value: Any):
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return {}
    return value


OptionalDict = Annotated[dict, BeforeValidator(convert_none_or_empty_string_to_dict)]
