# pylint: disable=C0103,C0114,C0115,C0116
"""Metadata carried beside the mapping instead of among its keys (GH #331).

`__is_block__`, `__comments__` and `__inline_comments__` are the serializer's,
but the names are not reserved in HCL: a document may declare an attribute
called any of them. In-band, one of the two has to lose -- on read the marker
overwrites the attribute, and on write `_is_reserved_key` drops it -- and the
caller cannot tell which happened, because by then the dict holds one value.

`metadata_sidecar=True` puts the three on the object instead. The mapping then
holds attributes and nothing else, so there is nothing to collide with.
"""

import json
from unittest import TestCase

from hcl2.api import dumps, loads
from hcl2.const import COMMENTS_KEY, INLINE_COMMENTS_KEY, IS_BLOCK
from hcl2.meta import HclDict, HclMeta, meta_of
from hcl2.utils import SerializationOptions

SIDECAR = SerializationOptions(metadata_sidecar=True)

RESERVED = (IS_BLOCK, COMMENTS_KEY, INLINE_COMMENTS_KEY)


class TestAnAttributeNamedLikeMetadataSurvives(TestCase):
    def test_it_is_read_as_an_attribute(self):
        for key in RESERVED:
            with self.subTest(key=key):
                body = loads(
                    f'resource "a" "b" {{\n  {key} = 99\n  keep = 1\n}}\n',
                    serialization_options=SIDECAR,
                )["resource"][0]['"a"']['"b"']
                self.assertEqual(body[key], 99)
                self.assertEqual(body["keep"], 1)

    def test_it_survives_a_round_trip(self):
        for key in RESERVED:
            with self.subTest(key=key):
                source = f'resource "a" "b" {{\n  {key} = 99\n  keep = 1\n}}\n'
                written = dumps(loads(source, serialization_options=SIDECAR))
                self.assertIn(key, written)
                self.assertIn("keep", written)

    def test_in_band_still_loses_it(self):
        # The behaviour the option exists to avoid, pinned so the difference
        # between the two modes stays visible.
        written = dumps(loads('resource "a" "b" {\n  __is_block__ = 99\n  keep = 1\n}\n'))
        self.assertNotIn("__is_block__", written)
        self.assertIn("keep", written)


class TestTheMetadataItself(TestCase):
    SOURCE = '# lead\nresource "a" "b" {\n  x = 1 # trailing\n}\n'

    def test_a_block_is_marked_on_the_object(self):
        body = loads(self.SOURCE, serialization_options=SIDECAR)["resource"][0]['"a"']['"b"']
        self.assertTrue(meta_of(body).is_block)
        self.assertNotIn(IS_BLOCK, body)

    def test_comments_match_what_the_in_band_form_carries(self):
        side = loads(self.SOURCE, serialization_options=SIDECAR)
        in_band = loads(self.SOURCE)
        self.assertEqual(meta_of(side).comments, in_band[COMMENTS_KEY])
        body = side["resource"][0]['"a"']['"b"']
        in_band_body = in_band["resource"][0]['"a"']['"b"']
        self.assertEqual(meta_of(body).comments, in_band_body[COMMENTS_KEY])

    def test_a_document_without_metadata_carries_an_empty_one(self):
        document = loads("x = 1\n", serialization_options=SIDECAR)
        self.assertTrue(meta_of(document).is_empty())


class TestItIsStillADict(TestCase):
    """Anything that reads attributes must not notice the change."""

    def setUp(self):
        self.body = loads('resource "a" "b" {\n  x = 1\n}\n', serialization_options=SIDECAR)["resource"][0][
            '"a"'
        ]['"b"']

    def test_equality_ignores_the_sidecar(self):
        self.assertEqual(self.body, {"x": 1})

    def test_json_serializes_the_attributes_alone(self):
        # JSON cannot carry the sidecar, which is why the in-band keys remain
        # the default rather than being replaced.
        self.assertEqual(json.loads(json.dumps(self.body)), {"x": 1})

    def test_it_is_a_dict(self):
        self.assertIsInstance(self.body, dict)
        self.assertEqual(list(self.body), ["x"])


class TestBothFormsAreAccepted(TestCase):
    """`dumps` reads whichever form it is handed, including a hand-built dict."""

    IN_BAND = {"resource": [{'"aws_instance"': {'"web"': {IS_BLOCK: True, "ami": '"ami-1"'}}}]}
    SIDECAR_DICT = {
        "resource": [{'"aws_instance"': {'"web"': HclDict({"ami": '"ami-1"'}, meta=HclMeta(is_block=True))}}]
    }
    EXPECTED = 'resource "aws_instance" "web" {\n  ami = "ami-1"\n}\n'

    def test_a_legacy_in_band_dict_still_writes(self):
        self.assertEqual(dumps(self.IN_BAND), self.EXPECTED)

    def test_a_sidecar_dict_writes_the_same(self):
        self.assertEqual(dumps(self.SIDECAR_DICT), dumps(self.IN_BAND))
        self.assertEqual(dumps(self.SIDECAR_DICT), self.EXPECTED)

    def test_a_nested_block_keeps_its_own_metadata(self):
        source = 'resource "a" "b" {\n  net {\n    i = 0\n  }\n}\n'
        outer = loads(source, serialization_options=SIDECAR)["resource"][0]['"a"']['"b"']
        inner = outer["net"][0]
        self.assertTrue(meta_of(outer).is_block)
        self.assertTrue(meta_of(inner).is_block)
        self.assertEqual(dumps(loads(source, serialization_options=SIDECAR)), source)


class TestTheDefaultIsUnchanged(TestCase):
    def test_metadata_still_arrives_in_band(self):
        body = loads('resource "a" "b" {\n  x = 1\n}\n')["resource"][0]['"a"']['"b"']
        self.assertTrue(body[IS_BLOCK])
        self.assertIsNone(meta_of(body))
