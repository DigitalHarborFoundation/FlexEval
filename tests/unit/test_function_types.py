import json
import unittest
from typing import Annotated, List, Union

from flexeval import function_types
from flexeval.classes import message, turn


def f_notype(p):
    pass


def f_str(p: str):
    pass


def f_list(p: list):
    pass


def f_str_or_list(p: str | list):
    pass


def f_message(p: message.Message):
    pass


def f_message_or_str(p: message.Message | str):
    pass


class TestGetAcceptableArgTypes(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(function_types.get_acceptable_arg_types(str), {str})
        self.assertEqual(function_types.get_acceptable_arg_types(list), {list})
        self.assertEqual(function_types.get_acceptable_arg_types(List), {list})
        self.assertEqual(function_types.get_acceptable_arg_types(list[int]), {list})

    def test_annotated(self):
        self.assertEqual(
            function_types.get_acceptable_arg_types(Annotated[str, "md"]), {str}
        )
        self.assertEqual(
            function_types.get_acceptable_arg_types(Annotated[list[str], "md"]), {list}
        )

    def test_union(self):
        self.assertEqual(function_types.get_acceptable_arg_types(str | int), {str, int})
        self.assertEqual(
            function_types.get_acceptable_arg_types(Union[str, int]), {str, int}
        )
        self.assertEqual(
            function_types.get_acceptable_arg_types(str | int | set), {str, int, set}
        )
        self.assertEqual(
            function_types.get_acceptable_arg_types(str | Union[int, set]),
            {str, int, set},
        )

    def test_combination(self):
        self.assertEqual(
            function_types.get_acceptable_arg_types(Annotated[list[str] | str, "md"]),
            {list, str},
        )
        self.assertEqual(
            function_types.get_acceptable_arg_types(
                Annotated[str, "md"] | Annotated[int, "md"]
            ),
            {str, int},
        )


class TestGetFirstParameterTypes(unittest.TestCase):
    def test_functions(self):
        self.assertEqual(function_types.get_first_parameter_types(f_notype), set())
        self.assertEqual(
            function_types.get_first_parameter_types(f_message), {message.Message}
        )
        self.assertEqual(function_types.get_first_parameter_types(f_str), {str})
        self.assertEqual(
            function_types.get_first_parameter_types(f_str_or_list), {str, list}
        )
        self.assertEqual(
            function_types.get_first_parameter_types(f_message_or_str),
            {message.Message, str},
        )

    def test_lambda(self):
        self.assertEqual(
            function_types.get_first_parameter_types(lambda x: x),
            set(),
            "Lambda functions should have no types.",
        )


class TestGetFunctionInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.message = message.Message(
            role="assistant",
            content="Response",
            context=json.dumps(
                [
                    {"role": "user", "content": "Messsage"},
                    {"role": "assistant", "content": "Response"},
                ]
            ),
            toolcalls=[],
        )
        cls.turn = turn.Turn(messages=[cls.message])

    def test_get_function_input(self):
        self.assertIsInstance(
            function_types.get_function_input(f_notype, "Message", self.message, False),
            message.Message,
        )
        self.assertIsInstance(
            function_types.get_function_input(
                f_message, "Message", self.message, False
            ),
            message.Message,
        )
        for context_only in [True, False]:
            self.assertIsInstance(
                function_types.get_function_input(
                    f_str, "Message", self.message, context_only
                ),
                str,
            )
        with self.assertRaises(ValueError):
            function_types.get_function_input(f_list, "Message", self.message, True)
        for context_only in [True, False]:
            for f in [f_list, f_str_or_list]:
                self.assertIsInstance(
                    function_types.get_function_input(
                        f, "Turn", self.turn, context_only
                    ),
                    list,
                )
