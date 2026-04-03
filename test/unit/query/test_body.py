# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView, BodyView, _collect_leading_comments


class TestDocumentView(TestCase):
    def test_parse(self):
        doc = DocumentView.parse("x = 1\n")
        self.assertIsInstance(doc, DocumentView)

    def test_body(self):
        doc = DocumentView.parse("x = 1\n")
        body = doc.body
        self.assertIsInstance(body, BodyView)

    def test_blocks(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {\n  ami = "test"\n}\n'
        )
        blocks = doc.blocks("resource")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "resource")

    def test_blocks_no_filter(self):
        doc = DocumentView.parse('resource "a" "b" {}\nvariable "c" {}\n')
        blocks = doc.blocks()
        self.assertEqual(len(blocks), 2)

    def test_blocks_with_labels(self):
        doc = DocumentView.parse(
            'resource "aws_instance" "main" {}\nresource "aws_s3_bucket" "data" {}\n'
        )
        blocks = doc.blocks("resource", "aws_instance")
        self.assertEqual(len(blocks), 1)

    def test_attributes(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        attrs = doc.attributes()
        self.assertEqual(len(attrs), 2)

    def test_attributes_filtered(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        attrs = doc.attributes("x")
        self.assertEqual(len(attrs), 1)

    def test_attribute(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        attr = doc.attribute("x")
        self.assertIsNotNone(attr)
        self.assertEqual(attr.name, "x")

    def test_attribute_missing(self):
        doc = DocumentView.parse("x = 1\n")
        attr = doc.attribute("missing")
        self.assertIsNone(attr)

    def test_parse_file(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as tmp:
            tmp.write("x = 1\n")
            tmp.flush()
            try:
                doc = DocumentView.parse_file(tmp.name)
                self.assertIsInstance(doc, DocumentView)
                attr = doc.attribute("x")
                self.assertIsNotNone(attr)
            finally:
                os.unlink(tmp.name)

    def test_blocks_label_too_many(self):
        doc = DocumentView.parse('resource "type" {}\n')
        # Ask for more labels than the block has
        blocks = doc.blocks("resource", "type", "extra")
        self.assertEqual(len(blocks), 0)

    def test_blocks_label_partial_mismatch(self):
        doc = DocumentView.parse('resource "aws_instance" "main" {}\n')
        blocks = doc.blocks("resource", "aws_s3_bucket")
        self.assertEqual(len(blocks), 0)


class TestBodyView(TestCase):
    def test_blocks(self):
        doc = DocumentView.parse('resource "a" "b" {}\n')
        body = doc.body
        blocks = body.blocks()
        self.assertEqual(len(blocks), 1)

    def test_attributes(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        body = doc.body
        attrs = body.attributes()
        self.assertEqual(len(attrs), 2)


class TestCollectLeadingComments(TestCase):
    """Tests for _collect_leading_comments helper."""

    def _body(self, hcl: str):
        doc = DocumentView.parse(hcl)
        return doc.body.raw  # BodyRule

    def test_comment_before_block(self):
        body = self._body('# about resource\nresource "a" "b" {}\n')
        # Find the BlockRule child
        from hcl2.rules.base import BlockRule

        for child in body.children:
            if isinstance(child, BlockRule):
                result = _collect_leading_comments(body, child.index)
                self.assertEqual(result, [{"value": "about resource"}])
                return
        self.fail("No BlockRule found")

    def test_comment_before_attribute(self):
        body = self._body("# about x\nx = 1\n")
        from hcl2.rules.base import AttributeRule

        for child in body.children:
            if isinstance(child, AttributeRule):
                result = _collect_leading_comments(body, child.index)
                self.assertEqual(result, [{"value": "about x"}])
                return
        self.fail("No AttributeRule found")

    def test_stops_at_previous_semantic_sibling(self):
        body = self._body("x = 1\n# about y\ny = 2\n")
        from hcl2.rules.base import AttributeRule

        attrs = [c for c in body.children if isinstance(c, AttributeRule)]
        # First attribute (x) — comment before it is empty (only bare newlines)
        result_x = _collect_leading_comments(body, attrs[0].index)
        self.assertEqual(result_x, [])
        # Second attribute (y) — has "about y" above it
        result_y = _collect_leading_comments(body, attrs[1].index)
        self.assertEqual(result_y, [{"value": "about y"}])

    def test_bare_newlines_not_collected(self):
        body = self._body("\n\nx = 1\n")
        from hcl2.rules.base import AttributeRule

        for child in body.children:
            if isinstance(child, AttributeRule):
                result = _collect_leading_comments(body, child.index)
                self.assertEqual(result, [])
                return
        self.fail("No AttributeRule found")

    def test_multiple_comments_in_order(self):
        body = self._body("# first\n# second\nx = 1\n")
        from hcl2.rules.base import AttributeRule

        for child in body.children:
            if isinstance(child, AttributeRule):
                result = _collect_leading_comments(body, child.index)
                self.assertEqual(result, [{"value": "first"}, {"value": "second"}])
                return
        self.fail("No AttributeRule found")

    def test_comment_between_two_blocks(self):
        body = self._body('resource "a" "b" {}\n# about variable\nvariable "c" {}\n')
        from hcl2.rules.base import BlockRule

        blocks = [c for c in body.children if isinstance(c, BlockRule)]
        self.assertEqual(len(blocks), 2)
        # First block: no leading comments
        self.assertEqual(_collect_leading_comments(body, blocks[0].index), [])
        # Second block: "about variable"
        self.assertEqual(
            _collect_leading_comments(body, blocks[1].index),
            [{"value": "about variable"}],
        )
