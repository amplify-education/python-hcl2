from io import StringIO
from unittest import TestCase

from hcl2.api import (
    load,
    loads,
    dump,
    dumps,
    parse,
    parses,
    parse_to_tree,
    parses_to_tree,
    from_dict,
    from_json,
    reconstruct,
    transform,
    serialize,
)
from hcl2.rules.base import StartRule
from hcl2.utils import SerializationOptions
from hcl2.deserializer import DeserializerOptions
from hcl2.formatter import FormatterOptions
from lark.tree import Tree


SIMPLE_HCL = 'x = 5\n'
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
        result = loads(SIMPLE_HCL, serialization_options=SerializationOptions(with_meta=True))
        self.assertIn("x", result)

    def test_block_parsing(self):
        result = loads(BLOCK_HCL)
        self.assertIn("resource", result)


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
        hcl = '# comment\nx = 5\n'
        result = parses(hcl, discard_comments=False)
        serialized = serialize(result)
        self.assertIn("__comments__", serialized)

    def test_discard_comments_true(self):
        hcl = '# comment\nx = 5\n'
        result = parses(hcl, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestParse(TestCase):

    def test_from_file(self):
        f = StringIO(SIMPLE_HCL)
        result = parse(f)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments(self):
        f = StringIO('# comment\nx = 5\n')
        result = parse(f, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestTransform(TestCase):

    def test_transforms_lark_tree(self):
        lark_tree = parses_to_tree(SIMPLE_HCL)
        result = transform(lark_tree)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments(self):
        lark_tree = parses_to_tree('# comment\nx = 5\n')
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
        result = from_dict(SIMPLE_DICT, format=False)
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
        result = from_json('{"x": 5}', format=False)
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
