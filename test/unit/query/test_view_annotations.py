# pylint: disable=C0103,C0114,C0115,C0116
"""The query views' return annotations name the class they actually return.

`blocks()` only ever appends a `BlockView` and `attributes()` only ever an
`AttributeView`, but both were annotated `List[NodeView]`. Under a strict type
checker that put `block_type`, `labels`, `name_labels` and `AttributeView.name`
out of reach without an `isinstance` narrowing or a cast for a runtime type
that is never anything else.

These assert the annotations rather than the runtime types, because a runtime
check passes either way -- it is only the declaration that was wrong.
"""

from typing import List, Optional, get_type_hints
from unittest import TestCase

from hcl2.query.attributes import AttributeView
from hcl2.query.blocks import BlockView
from hcl2.query.body import BodyView, DocumentView

# `blocks()` and `attributes()` import their view classes inside the method to
# break an import cycle, so the annotations resolve only against this mapping.
_NAMESPACE = {
    "AttributeView": AttributeView,
    "BlockView": BlockView,
    "BodyView": BodyView,
}


def _returns(method):
    return get_type_hints(method, localns=_NAMESPACE)["return"]


class TestBodyViewAnnotations(TestCase):
    def test_blocks_returns_block_views(self):
        self.assertEqual(_returns(BodyView.blocks), List[BlockView])

    def test_attributes_returns_attribute_views(self):
        self.assertEqual(_returns(BodyView.attributes), List[AttributeView])

    def test_attribute_returns_an_optional_attribute_view(self):
        self.assertEqual(_returns(BodyView.attribute), Optional[AttributeView])


class TestDocumentViewAnnotations(TestCase):
    """The document-level methods delegate to the body and must not re-widen."""

    def test_blocks_returns_block_views(self):
        self.assertEqual(_returns(DocumentView.blocks), List[BlockView])

    def test_attributes_returns_attribute_views(self):
        self.assertEqual(_returns(DocumentView.attributes), List[AttributeView])

    def test_attribute_returns_an_optional_attribute_view(self):
        self.assertEqual(_returns(DocumentView.attribute), Optional[AttributeView])


class TestBlockViewAnnotations(TestCase):
    def test_blocks_returns_block_views(self):
        self.assertEqual(_returns(BlockView.blocks), List[BlockView])

    def test_attributes_returns_attribute_views(self):
        self.assertEqual(_returns(BlockView.attributes), List[AttributeView])

    def test_attribute_returns_an_optional_attribute_view(self):
        self.assertEqual(_returns(BlockView.attribute), Optional[AttributeView])

    def test_body_returns_a_body_view(self):
        self.assertEqual(_returns(BlockView.body.fget), BodyView)


class TestAnnotationsMatchRuntime(TestCase):
    """The declarations above are only worth having if they stay true."""

    SOURCE = 'resource "aws_instance" "web" {\n  ami = "ami-1"\n}\n'

    def test_blocks_are_block_views(self):
        doc = DocumentView.parse(self.SOURCE)
        self.assertTrue(all(isinstance(block, BlockView) for block in doc.blocks()))

    def test_attributes_are_attribute_views(self):
        doc = DocumentView.parse(self.SOURCE)
        block = doc.blocks("resource")[0]
        self.assertTrue(all(isinstance(attr, AttributeView) for attr in block.attributes()))

    def test_block_body_is_a_body_view(self):
        doc = DocumentView.parse(self.SOURCE)
        self.assertIsInstance(doc.blocks("resource")[0].body, BodyView)
