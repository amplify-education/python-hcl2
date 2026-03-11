# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.path import PathSegment, parse_path
from hcl2.query.resolver import resolve_path


class TestResolvePathStructural(TestCase):
    def test_simple_attribute(self):
        doc = DocumentView.parse("x = 1\n")
        results = resolve_path(doc, parse_path("x"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "x")

    def test_block_type(self):
        doc = DocumentView.parse('resource "type" "name" {}\n')
        results = resolve_path(doc, parse_path("resource"))
        self.assertEqual(len(results), 1)

    def test_block_type_with_label(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {\n  ami = "test"\n}\n'
        )
        results = resolve_path(doc, parse_path("resource.aws_instance"))
        self.assertEqual(len(results), 1)

    def test_block_full_path(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {\n  ami = "test"\n}\n'
        )
        results = resolve_path(doc, parse_path("resource.aws_instance.main"))
        self.assertEqual(len(results), 1)

    def test_block_attribute(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {\n  ami = "test"\n}\n'
        )
        results = resolve_path(doc, parse_path("resource.aws_instance.main.ami"))
        self.assertEqual(len(results), 1)

    def test_wildcard_blocks(self):
        doc = DocumentView.parse('resource "a" "b" {}\nvariable "c" {}\n')
        results = resolve_path(doc, parse_path("*"))
        self.assertEqual(len(results), 2)

    def test_select_all(self):
        doc = DocumentView.parse('variable "a" {}\nvariable "b" {}\n')
        results = resolve_path(doc, parse_path("variable[*]"))
        self.assertEqual(len(results), 2)

    def test_index(self):
        doc = DocumentView.parse('variable "a" {}\nvariable "b" {}\n')
        results = resolve_path(doc, parse_path("variable[0]"))
        self.assertEqual(len(results), 1)

    def test_no_match(self):
        doc = DocumentView.parse("x = 1\n")
        results = resolve_path(doc, parse_path("nonexistent"))
        self.assertEqual(len(results), 0)

    def test_empty_segments(self):
        doc = DocumentView.parse("x = 1\n")
        results = resolve_path(doc, [])
        self.assertEqual(len(results), 1)  # returns root

    def test_label_mismatch(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        results = resolve_path(doc, parse_path("resource.aws_s3_bucket"))
        self.assertEqual(len(results), 0)

    def test_no_label_block(self):
        doc = DocumentView.parse("locals {\n  x = 1\n}\n")
        results = resolve_path(doc, parse_path("locals.x"))
        self.assertEqual(len(results), 1)

    def test_wildcard_labels(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {}\nresource "aws_s3_bucket" "data" {}\n'
        )
        results = resolve_path(doc, parse_path("resource[*].*"))
        self.assertEqual(len(results), 2)

    def test_attribute_unwrap_to_object(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        results = resolve_path(doc, parse_path("x.a"))
        self.assertEqual(len(results), 1)

    def test_attribute_unwrap_to_object_wildcard(self):
        doc = DocumentView.parse("x = {\n  a = 1\n  b = 2\n}\n")
        results = resolve_path(doc, parse_path("x.*"))
        self.assertEqual(len(results), 2)

    def test_tuple_select_all(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        results = resolve_path(
            doc,
            [
                PathSegment(name="x", select_all=False, index=None),
                PathSegment(name="*", select_all=True, index=None),
            ],
        )
        self.assertEqual(len(results), 3)

    def test_tuple_index(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        results = resolve_path(
            doc,
            [
                PathSegment(name="x", select_all=False, index=None),
                PathSegment(name="*", select_all=False, index=1),
            ],
        )
        self.assertEqual(len(results), 1)

    def test_tuple_index_out_of_range(self):
        doc = DocumentView.parse("x = [1, 2]\n")
        results = resolve_path(
            doc,
            [
                PathSegment(name="x", select_all=False, index=None),
                PathSegment(name="*", select_all=False, index=99),
            ],
        )
        self.assertEqual(len(results), 0)

    def test_tuple_no_match_without_index(self):
        doc = DocumentView.parse("x = [1, 2]\n")
        results = resolve_path(
            doc,
            [
                PathSegment(name="x", select_all=False, index=None),
                PathSegment(name="foo", select_all=False, index=None),
            ],
        )
        self.assertEqual(len(results), 0)

    def test_object_key_no_match(self):
        doc = DocumentView.parse("x = {\n  a = 1\n}\n")
        results = resolve_path(doc, parse_path("x.nonexistent"))
        self.assertEqual(len(results), 0)

    def test_wildcard_body_includes_attributes(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        results = resolve_path(doc, parse_path("*"))
        self.assertEqual(len(results), 2)

    def test_index_out_of_range_on_blocks(self):
        doc = DocumentView.parse('variable "a" {}\n')
        results = resolve_path(doc, parse_path("variable[99]"))
        self.assertEqual(len(results), 0)

    def test_resolve_on_unknown_node_type(self):
        doc = DocumentView.parse("x = 1\n")
        attr = doc.attribute("x")
        value_view = attr.value_node
        results = resolve_path(
            value_view, [PathSegment(name="foo", select_all=False, index=None)]
        )
        self.assertEqual(len(results), 0)

    def test_block_labels_consumed_then_body(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {\n  ami = "test"\n}\n'
        )
        results = resolve_path(doc, parse_path("resource.aws_instance.main.ami"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "ami")


class TestResolveRecursive(TestCase):
    def test_recursive_find_nested_attr(self):
        hcl = 'resource "type" "name" {\n  ami = "test"\n}\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("resource..ami"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "ami")

    def test_recursive_deeply_nested(self):
        hcl = (
            'resource "type" "name" {\n'
            '  provisioner "local-exec" {\n'
            '    command = "echo"\n'
            "  }\n"
            "}\n"
        )
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("resource..command"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "command")

    def test_recursive_multiple_matches(self):
        hcl = (
            'resource "a" "x" {\n  ami = "1"\n}\n'
            'resource "b" "y" {\n  ami = "2"\n}\n'
        )
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..ami"))
        self.assertEqual(len(results), 2)

    def test_recursive_no_match(self):
        hcl = 'resource "type" "name" {\n  ami = "test"\n}\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("resource..nonexistent"))
        self.assertEqual(len(results), 0)

    def test_recursive_from_root(self):
        hcl = 'resource "type" "name" {\n  ami = "test"\n}\n'
        doc = DocumentView.parse(hcl)
        # ".." from root should search everything
        results = resolve_path(
            doc,
            [PathSegment(name="ami", select_all=False, index=None, recursive=True)],
        )
        self.assertEqual(len(results), 1)

    def test_recursive_with_select_all(self):
        hcl = (
            'resource "a" "x" {\n  tag = "1"\n}\n'
            'resource "b" "y" {\n  tag = "2"\n}\n'
        )
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..tag[*]"))
        self.assertEqual(len(results), 2)


class TestTypeFilter(TestCase):
    def test_recursive_function_call_by_name(self):
        hcl = 'x = length(var.list)\ny = upper("hello")\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..function_call:length"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "length")

    def test_recursive_function_call_wildcard(self):
        hcl = 'x = length(var.list)\ny = upper("hello")\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..function_call:*[*]"))
        self.assertEqual(len(results), 2)

    def test_type_filter_attribute(self):
        hcl = 'resource "a" "b" {}\nx = 1\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(
            doc,
            [
                PathSegment(
                    name="*", select_all=True, index=None, type_filter="attribute"
                )
            ],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "x")

    def test_type_filter_block(self):
        hcl = 'resource "a" "b" {}\nx = 1\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(
            doc,
            [PathSegment(name="*", select_all=True, index=None, type_filter="block")],
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].block_type, "resource")

    def test_type_filter_no_match(self):
        hcl = "x = 1\n"
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..function_call:length"))
        self.assertEqual(len(results), 0)


class TestFunctionCallResolver(TestCase):
    def test_function_call_args(self):
        hcl = "x = length(var.list)\n"
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..function_call:length"))
        self.assertEqual(len(results), 1)
        # Navigate to args
        args = resolve_path(results[0], parse_path("args"))
        self.assertEqual(len(args), 1)

    def test_function_call_args_select_all(self):
        hcl = 'x = join(",", var.list)\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..function_call:join"))
        self.assertEqual(len(results), 1)
        args = resolve_path(
            results[0],
            [PathSegment(name="args", select_all=True, index=None)],
        )
        self.assertEqual(len(args), 2)

    def test_function_call_args_index(self):
        hcl = 'x = join(",", var.list)\n'
        doc = DocumentView.parse(hcl)
        results = resolve_path(doc, parse_path("*..function_call:join"))
        self.assertEqual(len(results), 1)
        args = resolve_path(
            results[0],
            [PathSegment(name="args", select_all=False, index=0)],
        )
        self.assertEqual(len(args), 1)


class TestSkipLabels(TestCase):
    """Test the ``~`` (skip labels) operator."""

    def test_skip_labels_basic(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {\n  ami = "test"\n}\n'
        )
        results = resolve_path(doc, parse_path("resource~.ami"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "ami")

    def test_skip_labels_wildcard(self):
        doc = DocumentView.parse(
            'resource "a" "x" {\n  ami = 1\n}\nresource "b" "y" {\n  ami = 2\n}\n'
        )
        results = resolve_path(doc, parse_path("resource~[*]"))
        self.assertEqual(len(results), 2)

    def test_skip_labels_with_select(self):
        doc = DocumentView.parse('block "a" {\n  x = 1\n}\nblock "b" {\n  y = 2\n}\n')
        results = resolve_path(doc, parse_path("block~[select(.x)]"))
        self.assertEqual(len(results), 1)

    def test_skip_labels_delegates_to_body(self):
        doc = DocumentView.parse('resource "aws" "main" {\n  tags = {}\n}\n')
        # Without ~ : need to consume labels
        r1 = resolve_path(doc, parse_path("resource.aws.main.tags"))
        self.assertEqual(len(r1), 1)
        # With ~ : skip labels directly
        r2 = resolve_path(doc, parse_path("resource~.tags"))
        self.assertEqual(len(r2), 1)

    def test_no_skip_labels_matches_labels(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {\n  ami = 1\n}\n')
        # Without ~, "aws_instance" matches the label
        results = resolve_path(doc, parse_path("resource.aws_instance"))
        self.assertEqual(len(results), 1)
