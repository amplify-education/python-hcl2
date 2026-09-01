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
