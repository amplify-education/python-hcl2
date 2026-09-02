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

import copy
import dataclasses
import json
import pickle
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


class TestCopyingCarriesTheSidecar(TestCase):
    """`document.copy()` is ordinary enough that losing metadata to it is a trap.

    `dict.copy` returns a plain `dict`, so an inherited copy would drop the
    sidecar and the block would then be written as an object. The in-band form
    survives a copy for free, because its metadata is among the keys; this has
    to say so explicitly.
    """

    def setUp(self):
        self.document = loads('resource "a" "b" {\n  x = 1\n}\n', serialization_options=SIDECAR)
        self.body = self.document["resource"][0]['"a"']['"b"']

    def test_the_dict_method(self):
        duplicate = self.body.copy()
        self.assertIsInstance(duplicate, HclDict)
        self.assertTrue(meta_of(duplicate).is_block)

    def test_copy_copy(self):
        self.assertTrue(meta_of(copy.copy(self.body)).is_block)

    def test_copy_deepcopy(self):
        duplicate = copy.deepcopy(self.body)
        self.assertTrue(meta_of(duplicate).is_block)
        self.assertIsNot(meta_of(duplicate), meta_of(self.body))

    def test_pickle(self):
        self.assertTrue(meta_of(pickle.loads(pickle.dumps(self.body))).is_block)

    def test_a_copied_document_still_writes_a_block(self):
        copied = copy.deepcopy(self.document)
        self.assertEqual(dumps(copied), dumps(self.document))

    def test_dict_of_it_is_a_plain_dict(self):
        # Deliberate: asking for a `dict` gives the mapping, nothing else.
        plain = dict(self.body)
        self.assertIsNone(meta_of(plain))
        self.assertEqual(plain, {"x": 1})


class TestAnObjectLiteralIsCoveredToo(TestCase):
    """The collision is not specific to block bodies.

    Only `BodyRule` was taught the sidecar at first, so `x = { __is_block__ =
    true }` still tripped the in-band branch: the object was read as a block
    and `dumps` emitted `x = keep = 1`, which is not HCL at all. An object
    literal carries no metadata of its own, but it has to say so in the same
    form a body does.
    """

    def _round_trip(self, source: str) -> str:
        return dumps(loads(source, serialization_options=SIDECAR))

    def test_each_reserved_name_survives_as_a_key(self):
        for key in RESERVED:
            with self.subTest(key=key):
                written = self._round_trip(f"x = {{\n  {key} = 99\n  keep = 1\n}}\n")
                self.assertIn(key, written)
                self.assertIn("keep", written)

    def test_an_ordinary_object_is_unchanged(self):
        self.assertEqual(self._round_trip("x = {\n  a = 1\n}\n"), "x = {\n  a = 1,\n}\n")


class TestTheOptionDidNotMoveTheOtherOnes(TestCase):
    """`SerializationOptions` is not `kw_only`, so field order is a contract.

    Inserting the new field among the block options changed what every
    positional argument after it meant -- silently, with no exception and no
    test to catch it. It is appended instead.
    """

    def test_metadata_sidecar_is_last(self):
        names = [f.name for f in dataclasses.fields(SerializationOptions)]
        self.assertEqual(names[-1], "metadata_sidecar")

    def test_the_earlier_fields_keep_their_positions(self):
        options = SerializationOptions(True, False, False, False, True, False, False, True, False)
        self.assertFalse(options.force_operation_parentheses)
        self.assertTrue(options.preserve_scientific_notation)
        self.assertFalse(options.metadata_sidecar)


class TestTheQueryLayerWritesToTheSidecar(TestCase):
    """`BlockView.to_dict` merges adjacent comments, and has to pick the form.

    Writing the in-band key onto a dict carrying a sidecar put it back among
    the attributes, where nothing reserves it any more -- so `dumps` emitted
    `__comments__ = [...]` as real HCL, which does not re-parse. Reading the
    in-band key there also found nothing, because the block's own comments had
    moved to the meta, so neither list was complete.
    """

    SOURCE = '# lead comment\nterraform {\n  required_version = ">= 1.0"\n}\n'

    def _to_dict(self, options):
        from hcl2.query import DocumentView

        return DocumentView.parse(self.SOURCE).blocks("terraform")[0].to_dict(options=options)

    def test_the_comment_lands_in_the_meta(self):
        body = self._to_dict(SerializationOptions(metadata_sidecar=True, with_comments=True))
        self.assertEqual(meta_of(body).comments, [{"value": "lead comment"}])
        self.assertNotIn(COMMENTS_KEY, body)

    def test_the_block_still_writes_as_a_block(self):
        body = self._to_dict(SerializationOptions(metadata_sidecar=True, with_comments=True))
        self.assertEqual(dumps({"terraform": [body]}), 'terraform {\n  required_version = ">= 1.0"\n}\n')

    def test_the_in_band_form_is_unchanged(self):
        body = self._to_dict(SerializationOptions(with_comments=True))
        self.assertEqual(body[COMMENTS_KEY], [{"value": "lead comment"}])
