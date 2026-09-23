# pylint: disable=C0103,C0114,C0115,C0116
"""The query views' return annotations name the class they actually return.

`blocks()` only ever appends a `BlockView` and `attributes()` only ever an
`AttributeView`, but both were annotated `List[NodeView]`. Under a strict type
checker that put `block_type`, `labels`, `name_labels` and `AttributeView.name`
out of reach without an `isinstance` narrowing or a cast for a runtime type
that is never anything else.

These assert the annotations rather than the runtime types, because a runtime
check passes either way -- it is only the declaration that was wrong.

They resolve them the way a consumer does: a bare `get_type_hints`, with no
namespace supplied. Passing one would hide a name the annotation cannot reach
on its own, which is the failure mode a forward reference invites.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional, get_type_hints
from unittest import TestCase

import hcl2
from hcl2.query import blocks as blocks_module
from hcl2.query import body as body_module
from hcl2.query.attributes import AttributeView
from hcl2.query.blocks import BlockView
from hcl2.query.body import BodyView, DocumentView

REPO_ROOT = Path(hcl2.__file__).resolve().parent.parent


def _returns(method):
    return get_type_hints(method)["return"]


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


class TestAnnotationsResolveUnaided(TestCase):
    """The names the annotations use have to live in the defining module.

    `get_type_hints` reads a function's own globals. While the view classes were
    imported inside the methods, every one of these annotations raised
    `NameError` for anyone who introspected them -- pydantic, a documentation
    builder, a runtime validator -- even though the classes were importable.
    """

    def test_body_module_binds_block_view(self):
        self.assertIs(body_module.BlockView, BlockView)

    def test_blocks_module_binds_body_view(self):
        self.assertIs(blocks_module.BodyView, BodyView)

    def test_every_annotated_member_resolves_without_a_namespace(self):
        members = [
            BodyView.blocks,
            BodyView.attributes,
            BodyView.attribute,
            DocumentView.blocks,
            DocumentView.attributes,
            DocumentView.attribute,
            DocumentView.body.fget,
            BlockView.blocks,
            BlockView.attributes,
            BlockView.attribute,
            BlockView.body.fget,
        ]
        for member in members:
            with self.subTest(member=member.__qualname__):
                self.assertIn("return", get_type_hints(member))


class TestTheyResolveWhicheverModuleLoadsFirst(TestCase):
    """`body` and `blocks` name each other, so each imports the other last.

    That is what makes the cycle work: by the time either bottom import runs,
    the importing module has already defined its own classes, so the other one
    finds them. It is also what makes it fragile -- a class added *below* one
    of those imports, or a tool that hoists it to the top, turns this into an
    `ImportError` or an annotation nothing can resolve.

    A single process cannot see any of that: whichever module the suite
    imported first is cached for every test after it. So each entry point gets
    a fresh interpreter, and the assertions above are re-run inside it.
    """

    ENTRY_POINTS = (
        "hcl2",
        "hcl2.query",
        "hcl2.query.body",
        "hcl2.query.blocks",
        "hcl2.query.attributes",
    )

    PROBE = """
import importlib, sys
importlib.import_module({entry!r})

from typing import List, Optional, get_type_hints
from hcl2.query.attributes import AttributeView
from hcl2.query.blocks import BlockView
from hcl2.query.body import BodyView, DocumentView
import hcl2.query.blocks as blocks_module
import hcl2.query.body as body_module

assert body_module.BlockView is BlockView
assert blocks_module.BodyView is BodyView

assert get_type_hints(BodyView.blocks)["return"] == List[BlockView]
assert get_type_hints(BodyView.attributes)["return"] == List[AttributeView]
assert get_type_hints(BodyView.attribute)["return"] == Optional[AttributeView]
assert get_type_hints(BlockView.blocks)["return"] == List[BlockView]
assert get_type_hints(BlockView.attributes)["return"] == List[AttributeView]
assert get_type_hints(BlockView.body.fget)["return"] is BodyView
assert get_type_hints(DocumentView.blocks)["return"] == List[BlockView]
"""

    def test_each_entry_point(self):
        for entry in self.ENTRY_POINTS:
            with self.subTest(entry=entry):
                result = subprocess.run(
                    [sys.executable, "-c", self.PROBE.format(entry=entry)],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_imports_stay_below_the_classes(self):
        """The ordering the cycle depends on, stated where it can be checked.

        Both modules must import the other after their last `class`, so a
        class appended to either file lands above it rather than below.
        """
        for module, imported in (("body", "blocks"), ("blocks", "body")):
            with self.subTest(module=module):
                source = (REPO_ROOT / "hcl2" / "query" / f"{module}.py").read_text()
                import_line = f"from hcl2.query.{imported} import "
                self.assertGreater(
                    source.index(import_line),
                    source.rindex("\nclass "),
                    f"hcl2/query/{module}.py must import {imported} below its classes",
                )
