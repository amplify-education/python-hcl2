# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.builtins import apply_builtin
from hcl2.query.path import QuerySyntaxError, parse_path
from hcl2.query.resolver import resolve_path


class TestKeysBuiltin(TestCase):
    def test_keys_on_object(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        results = resolve_path(doc, parse_path("x"))
        keys = apply_builtin("keys", results)
        self.assertEqual(len(keys), 1)
        # ObjectView keys
        self.assertEqual(sorted(keys[0]), ["a", "b"])

    def test_keys_on_body(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        keys = apply_builtin("keys", [doc.body])
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0], ["x", "y"])

    def test_keys_on_document(self):
        doc = DocumentView.parse('resource "a" "b" {}\nx = 1\n')
        keys = apply_builtin("keys", [doc])
        self.assertEqual(len(keys), 1)
        self.assertIn("resource", keys[0])
        self.assertIn("x", keys[0])

    def test_keys_on_block(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        blocks = doc.blocks("resource")
        keys = apply_builtin("keys", blocks)
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0], ["resource", "aws_instance", "main"])

    def test_keys_on_dict(self):
        keys = apply_builtin("keys", [{"a": 1, "b": 2}])
        self.assertEqual(len(keys), 1)
        self.assertEqual(sorted(keys[0]), ["a", "b"])


class TestValuesBuiltin(TestCase):
    def test_values_on_object(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        results = resolve_path(doc, parse_path("x"))
        vals = apply_builtin("values", results)
        self.assertEqual(len(vals), 1)
        self.assertEqual(len(vals[0]), 2)

    def test_values_on_tuple(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        results = resolve_path(doc, parse_path("x"))
        vals = apply_builtin("values", results)
        self.assertEqual(len(vals), 1)
        self.assertEqual(len(vals[0]), 3)

    def test_values_on_body(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        vals = apply_builtin("values", [doc.body])
        self.assertEqual(len(vals), 1)
        self.assertEqual(len(vals[0]), 2)

    def test_values_on_dict(self):
        vals = apply_builtin("values", [{"a": 1, "b": 2}])
        self.assertEqual(len(vals), 1)
        self.assertEqual(sorted(vals[0]), [1, 2])


class TestLengthBuiltin(TestCase):
    def test_length_on_tuple(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        results = resolve_path(doc, parse_path("x"))
        lengths = apply_builtin("length", results)
        self.assertEqual(lengths, [3])

    def test_length_on_object(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        results = resolve_path(doc, parse_path("x"))
        lengths = apply_builtin("length", results)
        self.assertEqual(lengths, [2])

    def test_length_on_body(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        lengths = apply_builtin("length", [doc.body])
        self.assertEqual(lengths, [2])

    def test_length_on_node_view(self):
        doc = DocumentView.parse("x = 1\n")
        results = resolve_path(doc, parse_path("x"))
        lengths = apply_builtin("length", results)
        self.assertEqual(lengths, [1])

    def test_length_on_list(self):
        lengths = apply_builtin("length", [[1, 2, 3]])
        self.assertEqual(lengths, [3])

    def test_length_on_string(self):
        lengths = apply_builtin("length", ["hello"])
        self.assertEqual(lengths, [5])


class TestUnknownBuiltin(TestCase):
    def test_unknown_raises(self):
        with self.assertRaises(QuerySyntaxError):
            apply_builtin("nope", [1])
