# pylint: disable=C0103,C0114,C0115,C0116
from io import StringIO
from unittest import TestCase

from lark.tree import Tree

from hcl2.api import (
    dump,
    dumps,
    from_dict,
    from_json,
    load,
    loads,
    parse,
    parse_to_tree,
    parses,
    parses_to_tree,
    query,
    reconstruct,
    serialize,
    transform,
)
from hcl2.deserializer import DeserializerOptions
from hcl2.formatter import FormatterOptions
from hcl2.rules.base import StartRule
from hcl2.utils import SerializationOptions

SIMPLE_HCL = "x = 5\n"
SIMPLE_DICT = {"x": 5}

BLOCK_HCL = 'resource "aws_instance" "example" {\n  ami = "abc-123"\n}\n'


class TestLoads(TestCase):
    def test_simple_attribute(self):
        result = loads(SIMPLE_HCL)
        self.assertEqual(result["x"], 5)

    def test_returns_dict(self):
        result = loads(SIMPLE_HCL)
        self.assertIsInstance(result, dict)

    def test_with_serialization_options(self):
        result = loads(SIMPLE_HCL, serialization_options=SerializationOptions(with_comments=False))
        self.assertIsInstance(result, dict)
        self.assertEqual(result["x"], 5)

    def test_with_meta_option(self):
        result = loads(BLOCK_HCL, serialization_options=SerializationOptions(with_meta=True))
        self.assertIn("resource", result)
        # Verify the option is accepted and produces a dict with expected content
        self.assertIsInstance(result, dict)

    def test_block_parsing(self):
        result = loads(BLOCK_HCL)
        self.assertIn("resource", result)

    def test_strip_string_quotes(self):
        result = loads(
            BLOCK_HCL,
            serialization_options=SerializationOptions(strip_string_quotes=True, explicit_blocks=False),
        )
        resource_list = result["resource"]
        self.assertEqual(len(resource_list), 1)
        block = resource_list[0]
        # Block label should have no surrounding quotes
        self.assertIn("aws_instance", block)
        inner = block["aws_instance"]
        self.assertIn("example", inner)
        body = inner["example"]
        # Attribute value should have no surrounding quotes
        self.assertEqual(body["ami"], "abc-123")
        # No __is_block__ marker
        self.assertNotIn("__is_block__", body)


class TestLoad(TestCase):
    def test_from_file(self):
        f = StringIO(SIMPLE_HCL)
        result = load(f)
        self.assertEqual(result["x"], 5)

    def test_with_serialization_options(self):
        f = StringIO(SIMPLE_HCL)
        result = load(f, serialization_options=SerializationOptions(with_comments=False))
        self.assertEqual(result["x"], 5)


class TestDumps(TestCase):
    def test_simple_attribute(self):
        result = dumps(SIMPLE_DICT)
        self.assertIsInstance(result, str)
        self.assertIn("x", result)
        self.assertIn("5", result)

    def test_dumps_contains_key_and_value(self):
        result = dumps(SIMPLE_DICT)
        self.assertIn("x", result)
        self.assertIn("5", result)

    def test_roundtrip(self):
        result = loads(dumps(SIMPLE_DICT))
        self.assertEqual(result, SIMPLE_DICT)

    def test_with_deserializer_options(self):
        result = dumps(SIMPLE_DICT, deserializer_options=DeserializerOptions())
        self.assertIsInstance(result, str)

    def test_with_formatter_options(self):
        result = dumps(SIMPLE_DICT, formatter_options=FormatterOptions())
        self.assertIsInstance(result, str)


class TestDump(TestCase):
    def test_writes_to_file(self):
        f = StringIO()
        dump(SIMPLE_DICT, f)
        output = f.getvalue()
        self.assertIn("x", output)
        self.assertIn("5", output)


class TestParsesToTree(TestCase):
    def test_returns_lark_tree(self):
        result = parses_to_tree(SIMPLE_HCL)
        self.assertIsInstance(result, Tree)

    def test_tree_has_start_rule(self):
        result = parses_to_tree(SIMPLE_HCL)
        self.assertEqual(result.data, "start")


class TestParseToTree(TestCase):
    def test_from_file(self):
        f = StringIO(SIMPLE_HCL)
        result = parse_to_tree(f)
        self.assertIsInstance(result, Tree)


class TestParses(TestCase):
    def test_returns_start_rule(self):
        result = parses(SIMPLE_HCL)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments_false(self):
        hcl = "# comment\nx = 5\n"
        result = parses(hcl, discard_comments=False)
        serialized = serialize(result)
        self.assertIn("__comments__", serialized)

    def test_discard_comments_true(self):
        hcl = "# comment\nx = 5\n"
        result = parses(hcl, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestParse(TestCase):
    def test_from_file(self):
        f = StringIO(SIMPLE_HCL)
        result = parse(f)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments(self):
        f = StringIO("# comment\nx = 5\n")
        result = parse(f, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestTransform(TestCase):
    def test_transforms_lark_tree(self):
        lark_tree = parses_to_tree(SIMPLE_HCL)
        result = transform(lark_tree)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments(self):
        lark_tree = parses_to_tree("# comment\nx = 5\n")
        result = transform(lark_tree, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestSerialize(TestCase):
    def test_returns_dict(self):
        tree = parses(SIMPLE_HCL)
        result = serialize(tree)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["x"], 5)

    def test_with_options(self):
        tree = parses(SIMPLE_HCL)
        result = serialize(tree, serialization_options=SerializationOptions(with_comments=False))
        self.assertIsInstance(result, dict)

    def test_none_options_uses_defaults(self):
        tree = parses(SIMPLE_HCL)
        result = serialize(tree, serialization_options=None)
        self.assertEqual(result["x"], 5)


class TestFromDict(TestCase):
    def test_returns_start_rule(self):
        result = from_dict(SIMPLE_DICT)
        self.assertIsInstance(result, StartRule)

    def test_roundtrip(self):
        tree = from_dict(SIMPLE_DICT)
        result = serialize(tree)
        self.assertEqual(result["x"], 5)

    def test_without_formatting(self):
        result = from_dict(SIMPLE_DICT, apply_format=False)
        self.assertIsInstance(result, StartRule)

    def test_with_deserializer_options(self):
        result = from_dict(SIMPLE_DICT, deserializer_options=DeserializerOptions())
        self.assertIsInstance(result, StartRule)

    def test_with_formatter_options(self):
        result = from_dict(SIMPLE_DICT, formatter_options=FormatterOptions())
        self.assertIsInstance(result, StartRule)


class TestFromJson(TestCase):
    def test_returns_start_rule(self):
        result = from_json('{"x": 5}')
        self.assertIsInstance(result, StartRule)

    def test_roundtrip(self):
        tree = from_json('{"x": 5}')
        result = serialize(tree)
        self.assertEqual(result["x"], 5)

    def test_without_formatting(self):
        result = from_json('{"x": 5}', apply_format=False)
        self.assertIsInstance(result, StartRule)


class TestReconstruct(TestCase):
    def test_from_start_rule(self):
        tree = parses(SIMPLE_HCL)
        result = reconstruct(tree)
        self.assertIsInstance(result, str)
        self.assertIn("x", result)

    def test_from_lark_tree(self):
        lark_tree = parses_to_tree(SIMPLE_HCL)
        result = reconstruct(lark_tree)
        self.assertIsInstance(result, str)
        self.assertIn("x", result)

    def test_roundtrip(self):
        tree = parses(SIMPLE_HCL)
        hcl_text = reconstruct(tree)
        reparsed = loads(hcl_text)
        self.assertEqual(reparsed["x"], 5)


class TestErrorPaths(TestCase):
    def test_loads_raises_on_invalid_hcl(self):
        with self.assertRaises(Exception):
            loads("this is {{{{ not valid hcl")

    def test_dumps_on_non_dict_raises_type_error(self):
        with self.assertRaises(TypeError):
            dumps("not a dict")

    def test_from_json_raises_on_invalid_json(self):
        with self.assertRaises(Exception):
            from_json("{not valid json")


class TestQuery(TestCase):
    def test_query_string(self):
        from hcl2.query.body import DocumentView

        result = query(SIMPLE_HCL)
        self.assertIsInstance(result, DocumentView)
        attr = result.attribute("x")
        self.assertIsNotNone(attr)

    def test_query_file_object(self):
        from hcl2.query.body import DocumentView

        f = StringIO(SIMPLE_HCL)
        result = query(f)
        self.assertIsInstance(result, DocumentView)
        attr = result.attribute("x")
        self.assertIsNotNone(attr)


class TestNegativeIntegerLiterals(TestCase):
    """`-3` loads as the int -3, without disturbing subtraction.

    MINUS serves as both the unary sign and the binary subtraction operator, so
    a negative integer cannot be folded into INT_LITERAL by the lexer without
    breaking `10 -3`. These cases pin both halves of that trade-off.
    """

    def test_negative_int_is_an_int(self):
        self.assertEqual(loads("x = -3\n"), {"x": -3})

    def test_negative_int_matches_negative_float_handling(self):
        self.assertEqual(loads("x = -3\ny = -3.5\n"), {"x": -3, "y": -3.5})

    def test_negative_ints_in_tuple(self):
        self.assertEqual(loads("x = [-1, 2, -30]\n"), {"x": [-1, 2, -30]})

    def test_negative_ints_in_object(self):
        self.assertEqual(loads("x = { a = -1, b = 2 }\n"), {"x": {"a": -1, "b": 2}})

    def test_spaced_subtraction_is_still_an_expression(self):
        self.assertEqual(loads("x = 10 - 3\n"), {"x": "${10 - 3}"})

    def test_tight_subtraction_is_still_an_expression(self):
        """`10 -3` is a subtraction, not two adjacent literals."""
        self.assertEqual(loads("x = 10 -3\n"), {"x": "${10 - 3}"})

    def test_negated_reference_is_still_an_expression(self):
        self.assertEqual(loads("x = -var.count\n"), {"x": "${-var.count}"})

    def test_negation_inside_a_larger_expression(self):
        self.assertEqual(loads("x = 1 + -3\n"), {"x": "${1 + -3}"})

    def test_parenthesised_negation_is_still_an_expression(self):
        self.assertEqual(loads("x = -(3)\n"), {"x": "${-(3)}"})

    def test_scientific_notation_is_unaffected(self):
        self.assertEqual(loads("x = -1e10\n"), {"x": "${-1e10}"})

    def test_round_trip_through_dumps(self):
        self.assertEqual(loads(dumps(loads("x = -3\n"))), {"x": -3})
