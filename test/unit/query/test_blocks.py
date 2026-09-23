# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.utils import SerializationOptions


class TestBlockView(TestCase):
    def test_block_type(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        block = doc.blocks("resource")[0]
        self.assertEqual(block.block_type, "resource")

    def test_labels(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        block = doc.blocks("resource")[0]
        self.assertEqual(block.labels, ["resource", "aws_instance", "main"])

    def test_name_labels(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        block = doc.blocks("resource")[0]
        self.assertEqual(block.name_labels, ["aws_instance", "main"])

    def test_body(self):
        doc = DocumentView.parse('resource "type" "name" {\n  ami = "test"\n}\n')
        block = doc.blocks("resource")[0]
        body = block.body
        self.assertIsNotNone(body)

    def test_nested_attribute(self):
        doc = DocumentView.parse('resource "type" "name" {\n  ami = "test"\n}\n')
        block = doc.blocks("resource")[0]
        attr = block.attribute("ami")
        self.assertIsNotNone(attr)
        self.assertEqual(attr.name, "ami")

    def test_nested_blocks(self):
        hcl = 'resource "type" "name" {\n  provisioner "local-exec" {\n    command = "echo"\n  }\n}\n'
        doc = DocumentView.parse(hcl)
        block = doc.blocks("resource")[0]
        inner = block.blocks("provisioner")
        self.assertEqual(len(inner), 1)

    def test_to_hcl(self):
        doc = DocumentView.parse('resource "type" "name" {\n  ami = "test"\n}\n')
        block = doc.blocks("resource")[0]
        hcl = block.to_hcl()
        self.assertIn("resource", hcl)
        self.assertIn("ami", hcl)

    def test_identifier_label(self):
        doc = DocumentView.parse("locals {\n  x = 1\n}\n")
        block = doc.blocks("locals")[0]
        self.assertEqual(block.block_type, "locals")
        self.assertEqual(block.name_labels, [])

    def test_attributes_list(self):
        doc = DocumentView.parse('resource "type" "name" {\n  a = 1\n  b = 2\n}\n')
        block = doc.blocks("resource")[0]
        attrs = block.attributes()
        self.assertEqual(len(attrs), 2)

    def test_attributes_filtered(self):
        doc = DocumentView.parse('resource "type" "name" {\n  a = 1\n  b = 2\n}\n')
        block = doc.blocks("resource")[0]
        attrs = block.attributes("a")
        self.assertEqual(len(attrs), 1)
        self.assertEqual(attrs[0].name, "a")


class TestBlockViewAdjacentComments(TestCase):
    """Tests for adjacent comment merging in BlockView.to_dict()."""

    _OPTS = SerializationOptions(with_comments=True)

    def test_adjacent_comments_at_outer_level(self):
        doc = DocumentView.parse('# about resource\nresource "type" "name" {\n  x = 1\n}\n')
        block = doc.blocks("resource")[0]
        result = block.to_dict(options=self._OPTS)
        # Adjacent comments go at outer level, alongside the label key
        self.assertEqual(result["__comments__"], [{"value": "about resource"}])
        self.assertNotIn("__comments__", result['"type"']['"name"'])

    def test_adjacent_separate_from_inner_comments(self):
        doc = DocumentView.parse('# adjacent\nresource "type" "name" {\n  # inner\n  x = 1\n}\n')
        block = doc.blocks("resource")[0]
        result = block.to_dict(options=self._OPTS)
        # Adjacent at outer level
        self.assertEqual(result["__comments__"], [{"value": "adjacent"}])
        # Inner stays in body dict under __comments__
        body = result['"type"']['"name"']
        self.assertEqual(body["__comments__"], [{"value": "inner"}])

    def test_no_comments_without_option(self):
        doc = DocumentView.parse('# about\nresource "type" "name" {}\n')
        block = doc.blocks("resource")[0]
        result = block.to_dict()
        self.assertNotIn("__comments__", result)

    def test_no_labels_block_merges_adjacent_and_inner(self):
        doc = DocumentView.parse("# about locals\nlocals {\n  # inner\n  x = 1\n}\n")
        block = doc.blocks("locals")[0]
        result = block.to_dict(options=self._OPTS)
        # No name labels -> body dict IS the top level, so they merge
        self.assertEqual(
            result["__comments__"],
            [{"value": "about locals"}, {"value": "inner"}],
        )

    def test_single_label_block(self):
        doc = DocumentView.parse('# about var\nvariable "name" {\n  default = 1\n}\n')
        block = doc.blocks("variable")[0]
        result = block.to_dict(options=self._OPTS)
        self.assertEqual(result["__comments__"], [{"value": "about var"}])

    def test_no_adjacent_comments(self):
        doc = DocumentView.parse('resource "type" "name" {\n  x = 1\n}\n')
        block = doc.blocks("resource")[0]
        result = block.to_dict(options=self._OPTS)
        self.assertNotIn("__comments__", result)


class TestBlockViewLines(TestCase):
    """`start_line` / `end_line` report the span `with_meta` serializes.

    The line numbers were reachable only by serializing the block with
    `with_meta=True` and digging past the label nesting, or by reading the
    rule's private `_meta`. Both are what these properties replace.
    """

    NESTED = 'resource "aws_instance" "web" {\n  ami = "ami-1"\n\n  network_interface {\n    x = 0\n  }\n}\n'

    def test_span_of_a_top_level_block(self):
        block = DocumentView.parse(self.NESTED).blocks("resource")[0]
        self.assertEqual((block.start_line, block.end_line), (1, 7))

    def test_span_of_a_nested_block(self):
        block = DocumentView.parse(self.NESTED).blocks("resource")[0]
        nested = block.blocks("network_interface")[0]
        self.assertEqual((nested.start_line, nested.end_line), (4, 6))

    def test_an_empty_block_spans_one_line(self):
        block = DocumentView.parse('variable "x" {}\n').blocks("variable")[0]
        self.assertEqual((block.start_line, block.end_line), (1, 1))

    def test_agrees_with_with_meta(self):
        block = DocumentView.parse(self.NESTED).blocks("resource")[0]
        body = block.to_dict(options=SerializationOptions(with_meta=True))['"aws_instance"']['"web"']
        self.assertEqual(block.start_line, body["__start_line__"])
        self.assertEqual(block.end_line, body["__end_line__"])

    def test_a_block_without_a_position_reports_none(self):
        # A tree built by the deserializer carries an empty Meta.
        from hcl2.api import from_dict
        from hcl2.query.body import DocumentView as Doc

        tree = from_dict({"resource": [{"aws_instance": {"web": {"__is_block__": True}}}]})
        block = Doc(tree).blocks("resource")[0]
        self.assertIsNone(block.start_line)
        self.assertIsNone(block.end_line)
