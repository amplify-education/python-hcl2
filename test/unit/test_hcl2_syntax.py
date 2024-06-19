# pylint:disable=C0114,C0116,C0103,W0612

import string  # pylint:disable=W4901 # https://stackoverflow.com/a/16651393
from unittest import TestCase

from test.helpers.hcl2_helper import Hcl2Helper

from lark import UnexpectedToken, UnexpectedCharacters


class TestHcl2Syntax(Hcl2Helper, TestCase):
    """Test parsing individual elements of HCL2 syntax"""

    def test_argument(self):
        syntax = self.build_argument("identifier", '"expression"')
        result = self.load_to_dict(syntax)
        self.assertDictEqual(result, {"identifier": "expression"})

    def test_identifier_starts_with_digit(self):
        for i in range(0, 10):
            argument = self.build_argument(f"{i}id")
            with self.assertRaises(UnexpectedToken) as e:
                self.load_to_dict(argument)
                assert (
                    f"Unexpected token Token('DECIMAL', '{i}') at line 1, column 1"
                    in str(e)
                )

    def test_identifier_starts_with_special_chars(self):
        chars = string.punctuation.replace("_", "")
        for i in chars:
            argument = self.build_argument(f"{i}id")
            with self.assertRaises((UnexpectedToken, UnexpectedCharacters)) as e:
                self.load_to_dict(argument)

    def test_identifier_contains_special_chars(self):
        chars = string.punctuation.replace("_", "").replace("-", "")
        for i in chars:
            argument = self.build_argument(f"identifier{i}")
            with self.assertRaises((UnexpectedToken, UnexpectedCharacters)) as e:
                self.load_to_dict(argument)

    def test_identifier(self):
        argument = self.build_argument("_-__identifier_-1234567890-_")
        self.load_to_dict(argument)

    def test_block_no_labels(self):
        block = """
        block {
        }
        """
        result = self.load_to_dict(block)
        self.assertDictEqual(result, {"block": [{}]})

    def test_block_single_label(self):
        block = """
        block "label" {
        }
        """
        result = self.load_to_dict(block)
        self.assertDictEqual(result, {"block": [{"label": {}}]})

    def test_block_multiple_labels(self):
        block = """
        block "label1" "label2" "label3" {
        }
        """
        result = self.load_to_dict(block)
        self.assertDictEqual(
            result, {"block": [{"label1": {"label2": {"label3": {}}}}]}
        )

    def test_unary_operation(self):
        operations = [
            ("identifier = -10", {"identifier": "${-10}"}),
            ("identifier = !true", {"identifier": "${!True}"}),
        ]
        for hcl, dict_ in operations:
            result = self.load_to_dict(hcl)
            self.assertDictEqual(result, dict_)

    def test_tuple(self):
        tuple_ = """tuple = [
        identifier,
        "string", 100,
        true == false,
        5 + 5, function(),
        ]"""
        result = self.load_to_dict(tuple_)
        self.assertDictEqual(
            result,
            {
                "tuple": [
                    "${identifier}",
                    "string",
                    100,
                    "${True == False}",
                    "${5 + 5}",
                    "${function()}",
                ]
            },
        )

    def test_object(self):
        object_ = """object = {
        key1: identifier, key2: "string", key3: 100,
        key4: true == false,
        key5: 5 + 5, key6: function(),
        }"""
        result = self.load_to_dict(object_)
        self.assertDictEqual(
            result,
            {
                "object": {
                    "key1": "${identifier}",
                    "key2": "string",
                    "key3": 100,
                    "key4": "${True == False}",
                    "key5": "${5 + 5}",
                    "key6": "${function()}",
                }
            },
        )

    def test_function_call_and_arguments(self):
        calls = {
            "r = function()": {"r": "${function()}"},
            "r = function(arg1, arg2)": {"r": "${function(arg1, arg2)}"},
            """r = function(
                        arg1, arg2,
                        arg3,
                    )
            """: {
                "r": "${function(arg1, arg2, arg3)}"
            },
        }

        for call, expected in calls.items():
            result = self.load_to_dict(call)
            self.assertDictEqual(result, expected)

    def test_index(self):
        indexes = {
            "r = identifier[10]": {"r": "${identifier[10]}"},
            "r = identifier.20": {
                "r": "${identifier[2]}"
            },  # TODO debug why `20` is parsed to `2`
            """r = identifier["key"]""": {"r": '${identifier["key"]}'},
            """r = identifier.key""": {"r": "${identifier.key}"},
        }
        for call, expected in indexes.items():
            result = self.load_to_dict(call)
            self.assertDictEqual(result, expected)
