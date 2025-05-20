from typing import Union

from flexeval.classes.message import Message
from flexeval.classes.turn import Turn


def this_function_returns_true(*args, **kwargs):
    return True


def count_emojis(turn: str) -> int:
    return "overridden"
