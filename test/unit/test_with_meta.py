# pylint: disable=C0103,C0114,C0115,C0116
"""Regression tests for GH issue #291: `with_meta` produced no metadata.

`SerializationOptions.with_meta` documents `__start_line__` and `__end_line__`
keys, `hcl2tojson` exposes it as `--with-meta`, and the v8 migration guide says
the v7 keys "are still available". None of that was true: v7 emitted the keys
from `RuleTransformer.block`, and the v8 rewrite moved block serialization to
`BlockRule.serialize` without carrying them over, leaving the option read
nowhere in the package.

Line numbers below were checked against python-hcl2 7.3.1 on the same input,
so the values are v7's, not merely self-consistent.
"""

from unittest import TestCase

from hcl2.api import dumps, from_dict, loads, serialize
from hcl2.const import COMMENTS_KEY, END_LINE, INLINE_COMMENTS_KEY, IS_BLOCK, START_LINE
from hcl2.query.body import DocumentView
from hcl2.utils import SerializationOptions

_META = SerializationOptions(with_meta=True)

NESTED_HCL = """resource "aws_instance" "web" {
  ami = "ami-1"

  network_interface {
    device_index = 0
  }
}

variable "x" {}
"""


class TestWithMetaEmitsLineNumbers(TestCase):
    def test_block_carries_its_line_span(self):
        result = loads(NESTED_HCL, serialization_options=_META)
        body = result["resource"][0]['"aws_instance"']['"web"']
        self.assertEqual(body[START_LINE], 1)
        self.assertEqual(body[END_LINE], 7)

    def test_nested_block_carries_its_own_span(self):
        result = loads(NESTED_HCL, serialization_options=_META)
        body = result["resource"][0]['"aws_instance"']['"web"']
        interface = body["network_interface"][0]
        self.assertEqual(interface[START_LINE], 4)
        self.assertEqual(interface[END_LINE], 6)

    def test_empty_block_spans_one_line(self):
        result = loads(NESTED_HCL, serialization_options=_META)
        body = result["variable"][0]['"x"']
        self.assertEqual(body[START_LINE], 9)
        self.assertEqual(body[END_LINE], 9)

    def test_off_by_default(self):
        result = loads(NESTED_HCL)
        body = result["resource"][0]['"aws_instance"']['"web"']
        self.assertNotIn(START_LINE, body)
        self.assertNotIn(END_LINE, body)

    def test_attributes_get_no_metadata(self):
        # An attribute serializes to its own {name: value} pair, so there is
        # nowhere to put the keys. v7 did not annotate attributes either.
        result = loads("x = 1\n", serialization_options=_META)
        self.assertEqual(result, {"x": 1})

    def test_independent_of_explicit_blocks(self):
        options = SerializationOptions(with_meta=True, explicit_blocks=False)
        result = loads(NESTED_HCL, serialization_options=options)
        body = result["resource"][0]['"aws_instance"']['"web"']
        self.assertNotIn(IS_BLOCK, body)
        self.assertEqual(body[START_LINE], 1)


class TestWithMetaRoundTrip(TestCase):
    """The keys are metadata, so `dumps()` must not write them back as HCL."""

    def test_metadata_keys_are_not_emitted_as_attributes(self):
        data = loads(NESTED_HCL, serialization_options=_META)
        hcl = dumps(data)
        self.assertNotIn(START_LINE, hcl)
        self.assertNotIn(END_LINE, hcl)

    def test_round_trip_matches_output_without_metadata(self):
        with_meta = dumps(loads(NESTED_HCL, serialization_options=_META))
        without = dumps(loads(NESTED_HCL))
        self.assertEqual(with_meta, without)

    def test_a_tree_without_positions_reports_no_lines(self):
        # A tree built by the deserializer carries an empty Meta. Asking for
        # metadata there must skip the keys rather than raise or invent zeros.
        tree = from_dict({"resource": [{"aws_instance": {"web": {IS_BLOCK: True}}}]})
        result = serialize(tree, serialization_options=_META)
        body = result["resource"][0]["aws_instance"]["web"]
        self.assertNotIn(START_LINE, body)
        self.assertNotIn(END_LINE, body)


class TestUserAttributesNamedLikeMetadata(TestCase):
    """An attribute genuinely named `__start_line__` collides with the metadata.

    The keys are carried in-band, in the same dict as the block's attributes,
    which is where v7 put them and what the migration guide promises. That has
    a cost: the deserializer cannot tell a metadata key it wrote from an
    attribute the document really declared, so it drops both -- exactly as it
    already dropped `__is_block__` and `__comments__` before these two keys
    existed. `with_meta` additionally overwrites such an attribute.

    These pin the behaviour rather than bless it. Anything that made the
    metadata unambiguous would have to move all five keys out of band, which is
    a breaking change to the serialized shape, not a fix to this option.
    """

    RESERVED = (START_LINE, END_LINE, IS_BLOCK, COMMENTS_KEY, INLINE_COMMENTS_KEY)

    def test_a_reserved_name_does_not_survive_a_round_trip(self):
        for key in self.RESERVED:
            with self.subTest(key=key):
                hcl = f'block "a" {{\n  {key} = 99\n  keep = 1\n}}\n'
                written = dumps(loads(hcl))
                self.assertNotIn(key, written)
                self.assertIn("keep", written)

    def test_with_meta_overwrites_an_attribute_of_the_same_name(self):
        hcl = 'block "a" {\n  __start_line__ = 99\n}\n'
        body = loads(hcl, serialization_options=_META)["block"][0]['"a"']
        self.assertEqual(body[START_LINE], 1)

    def test_an_ordinary_dunder_attribute_is_untouched(self):
        # Only the five names are reserved; nothing about the leading
        # underscores makes an attribute metadata.
        hcl = 'block "a" {\n  __line__ = 99\n}\n'
        self.assertIn("__line__", dumps(loads(hcl)))


class TestSpansLandOnTheRightLines(TestCase):
    r"""Every block's span checked against where the block really sits.

    Asserting the lines a block actually occupies, rather than a pair of
    numbers, keeps the cases below readable and catches the shapes that break
    line counting rather than the ones that happen to be easy to write down.

    A heredoc is the one worth the trouble: its body arrives as a single token
    spanning several physical lines, so anything counting tokens rather than
    newlines gets every block after it wrong. Same for CRLF, where the line
    ending is two characters, and for comments, which the lexer discards.
    """

    CASES = {
        "a heredoc before the block": 'a = <<EOT\nl1\nl2\nEOT\n\nr "x" {\n  y = 1\n}\n',
        "a heredoc inside the block": ('r "x" {\n  s = <<E\nl1\nl2\nE\n  z = 1\n}\n\nr "y" {\n  w = 2\n}\n'),
        "crlf line endings": 'r "x" {\r\n  y = 1\r\n}\r\n\r\nr "y" {\r\n  z = 2\r\n}\r\n',
        "a block comment above": '/* one\n   two\n   three */\nr "x" {\n  y = 1\n}\n',
        "hash comments around": '# one\n# two\nr "x" {\n  # inner\n  y = 1\n}\n',
        "an inline comment on the header": 'r "x" { # trailing\n  y = 1\n}\n',
        "blank lines everywhere": '\n\n\nr "x" {\n\n\n  y = 1\n\n\n}\n\n',
        "four levels of nesting": (
            'a "1" {\n  b "2" {\n    c "3" {\n      d "4" {\n        x = 1\n      }\n    }\n  }\n}\n'
        ),
        "a single-line block": 'r "x" { y = 1 }\n',
    }

    def all_blocks(self, view):
        for block in view.blocks():
            yield block
            yield from self.all_blocks(block.body)

    def test_each_span_brackets_its_block(self):
        for name, source in self.CASES.items():
            lines = source.replace("\r\n", "\n").split("\n")
            doc = DocumentView.parse(source)
            blocks = list(self.all_blocks(doc))
            self.assertTrue(blocks, f"{name}: parsed no blocks")
            for block in blocks:
                with self.subTest(case=name, block=block.block_type):
                    start, end = block.start_line, block.end_line
                    self.assertIsNotNone(start, f"{name}: no span")
                    header = lines[start - 1]
                    self.assertIn(block.block_type, header)
                    self.assertIn("{", header)
                    self.assertIn("}", lines[end - 1])

    def test_the_serialized_keys_agree_with_the_properties(self):
        """`with_meta` and the query properties read the same `Meta`."""
        for name, source in self.CASES.items():
            with self.subTest(case=name):
                doc = DocumentView.parse(source)
                for block in self.all_blocks(doc):
                    body = block.to_dict(options=_META)
                    for _ in block.name_labels:
                        body = next(iter(body.values()))
                    self.assertEqual(body[START_LINE], block.start_line)
                    self.assertEqual(body[END_LINE], block.end_line)


class TestParityWithV7(TestCase):
    """The spans 7.3.1 reports for the same document, as a fixture.

    Checked against python-hcl2 7.3.1 rather than derived from this
    implementation, so a change in how lines are counted shows up as a
    disagreement with the version whose behaviour `with_meta` promises.
    Covers a block with no labels, one label and two, and two levels of
    nesting, since the keys land on the innermost dict the labels nest around.
    """

    SOURCE = """terraform {
  required_version = ">= 1.0"
}

# a leading comment
resource "aws_instance" "web" {
  ami = "ami-1"

  network_interface {
    device_index = 0

    nested_deeper {
      z = 1
    }
  }

  tags = {
    Name = "x"
  }
}

variable "empty" {}

locals {
  a = 1
}

module "m" {
  source = "./x"
}
"""

    V7_SPANS = {
        "terraform": (1, 3),
        "resource": (6, 20),
        "network_interface": (9, 15),
        "nested_deeper": (12, 14),
        "variable": (22, 22),
        "locals": (24, 26),
        "module": (28, 30),
    }

    def test_every_span_matches_v7(self):
        doc = DocumentView.parse(self.SOURCE)
        found = {}

        def collect(view):
            for block in view.blocks():
                found[block.block_type] = (block.start_line, block.end_line)
                collect(block.body)

        collect(doc)
        self.assertEqual(found, self.V7_SPANS)

    def test_an_object_valued_attribute_gets_no_span(self):
        # `tags = { ... }` is an attribute, not a block. v7 annotated only
        # blocks, and an object nests exactly like a labelless block's body,
        # so a span there would be indistinguishable from a real one.
        result = loads(self.SOURCE, serialization_options=_META)
        tags = result["resource"][0]['"aws_instance"']['"web"']["tags"]
        self.assertNotIn(START_LINE, tags)
        self.assertNotIn(END_LINE, tags)
        self.assertEqual(set(tags), {"Name"})
