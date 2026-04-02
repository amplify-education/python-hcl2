"""Specialized integration tests for specific features and scenarios.

Unlike the suite-based round-trip tests, these target individual features
(operator precedence, Builder round-trip) with dedicated golden files
in test/integration/special/.
"""

# pylint: disable=C0103,C0114,C0115,C0116

import json
from pathlib import Path
from typing import Optional
from unittest import TestCase

from test.integration.test_round_trip import (
    _parse_and_serialize,
    _deserialize_and_reserialize,
    _deserialize_and_reconstruct,
    _direct_reconstruct,
)

from hcl2.deserializer import BaseDeserializer, DeserializerOptions
from hcl2.formatter import BaseFormatter
from hcl2.reconstructor import HCLReconstructor
from hcl2.utils import SerializationOptions

SPECIAL_DIR = Path(__file__).absolute().parent / "specialized"


class TestOperatorPrecedence(TestCase):
    """Test that parsed expressions correctly represent operator precedence.

    Serializes with force_operation_parentheses=True so that implicit
    precedence becomes explicit parentheses in the output.
    See: https://github.com/amplify-education/python-hcl2/issues/248
    """

    maxDiff = None
    _OPTIONS = SerializationOptions(force_operation_parentheses=True)

    def test_operator_precedence(self):
        hcl_path = SPECIAL_DIR / "operator_precedence.tf"
        json_path = SPECIAL_DIR / "operator_precedence.json"

        actual = _parse_and_serialize(hcl_path.read_text(), options=self._OPTIONS)
        expected = json.loads(json_path.read_text())

        self.assertEqual(actual, expected)


class TestBuilderRoundTrip(TestCase):
    """Test that dicts produced by Builder can be deserialized, reconstructed to
    valid HCL, and reparsed back to equivalent dicts.

    Pipeline: Builder.build() → from_dict → reconstruct → HCL text
              HCL text → parse → serialize → dict (compare with expected)
    """

    maxDiff = None

    def _load_special(self, name, suffix):
        return (SPECIAL_DIR / f"{name}{suffix}").read_text()

    def test_builder_reconstruction(self):
        """Builder dict → deserialize → reconstruct → compare with expected HCL."""
        builder_dict = json.loads(self._load_special("builder_basic", ".json"))
        actual_hcl = _deserialize_and_reconstruct(builder_dict)
        expected_hcl = self._load_special("builder_basic", ".tf")
        self.assertMultiLineEqual(actual_hcl, expected_hcl)

    def test_builder_full_round_trip(self):
        """Builder dict → reconstruct → reparse → compare with expected JSON."""
        builder_dict = json.loads(self._load_special("builder_basic", ".json"))
        reconstructed_hcl = _deserialize_and_reconstruct(builder_dict)
        actual = _parse_and_serialize(reconstructed_hcl)
        expected = json.loads(self._load_special("builder_basic_reparsed", ".json"))
        self.assertEqual(actual, expected)

    def test_builder_reserialization(self):
        """Builder dict → deserialize → reserialize → compare with expected dict."""
        builder_dict = json.loads(self._load_special("builder_basic", ".json"))
        reserialized = _deserialize_and_reserialize(builder_dict)
        expected = json.loads(self._load_special("builder_basic_reserialized", ".json"))
        self.assertEqual(reserialized, expected)


def _deserialize_and_reconstruct_with_options(
    serialized: dict,
    deserializer_options: Optional[DeserializerOptions] = None,
) -> str:
    """Deserialize a Python dict and reconstruct HCL text with custom options."""
    deserializer = BaseDeserializer(deserializer_options)
    formatter = BaseFormatter()
    reconstructor = HCLReconstructor()
    deserialized = deserializer.load_python(serialized)
    formatter.format_tree(deserialized)
    lark_tree = deserialized.to_lark()
    return reconstructor.reconstruct(lark_tree)


class TestTemplateDirectives(TestCase):
    """Test template directives (%{if}, %{for}) parsing, serialization, and round-trip.

    Covers: basic if/else/endif, for/endfor, strip markers, escaped quotes in
    directive expressions (issue #247), nested directives, and escaped directives.
    """

    maxDiff = None

    def _load_special(self, name, suffix):
        return (SPECIAL_DIR / f"{name}{suffix}").read_text()

    def test_hcl_to_json(self):
        """HCL with directives -> JSON serialization matches expected."""
        hcl_text = self._load_special("template_directives", ".tf")
        actual = _parse_and_serialize(hcl_text)
        expected = json.loads(self._load_special("template_directives", ".json"))
        self.assertEqual(actual, expected)

    def test_direct_reconstruct(self):
        """HCL -> IR -> Lark -> HCL matches original."""
        hcl_text = self._load_special("template_directives", ".tf")
        actual = _direct_reconstruct(hcl_text)
        self.assertMultiLineEqual(actual, hcl_text)

    def test_json_reserialization(self):
        """JSON -> deserialize -> reserialize matches expected."""
        hcl_text = self._load_special("template_directives", ".tf")
        serialized = _parse_and_serialize(hcl_text)
        actual = _deserialize_and_reserialize(serialized)
        expected = json.loads(
            self._load_special("template_directives_reserialized", ".json")
        )
        self.assertEqual(actual, expected)

    def test_json_to_hcl(self):
        """JSON -> deserialize -> reconstruct matches expected HCL."""
        hcl_text = self._load_special("template_directives", ".tf")
        serialized = _parse_and_serialize(hcl_text)
        actual = _deserialize_and_reconstruct(serialized)
        expected = self._load_special("template_directives_reconstructed", ".tf")
        self.assertMultiLineEqual(actual, expected)

    def test_full_round_trip(self):
        """HCL -> JSON -> HCL -> JSON produces identical JSON."""
        hcl_text = self._load_special("template_directives", ".tf")
        serialized = _parse_and_serialize(hcl_text)
        reconstructed = _deserialize_and_reconstruct(serialized)
        reserialized = _parse_and_serialize(reconstructed)
        self.assertEqual(reserialized, serialized)


class TestCommentSerialization(TestCase):
    """Test that comments are correctly classified during HCL → JSON serialization.

    Covers:
    - Standalone comments (// and #) at body level → __comments__
    - Standalone comments absorbed by binary_op grammar → __comments__
    - Comments inside expressions (objects) → __inline_comments__
    - Multi-line block comments → __comments__
    - Comments in nested blocks
    - Top-level comments
    """

    maxDiff = None
    _OPTIONS = SerializationOptions(with_comments=True)

    def test_comment_classification(self):
        hcl_path = SPECIAL_DIR / "comments.tf"
        json_path = SPECIAL_DIR / "comments.json"

        actual = _parse_and_serialize(hcl_path.read_text(), options=self._OPTIONS)
        expected = json.loads(json_path.read_text())

        self.assertEqual(actual, expected)

    def test_top_level_comments(self):
        actual = _parse_and_serialize("// file header\nx = 1\n", options=self._OPTIONS)
        self.assertEqual(actual["__comments__"], [{"value": "file header"}])

    def test_standalone_in_body(self):
        actual = _parse_and_serialize(
            'resource "a" "b" {\n  # standalone\n  x = 1\n}\n',
            options=self._OPTIONS,
        )
        block = actual["resource"][0]['"a"']['"b"']
        self.assertEqual(block["__comments__"], [{"value": "standalone"}])
        self.assertNotIn("__inline_comments__", block)

    def test_absorbed_after_binary_op(self):
        actual = _parse_and_serialize(
            "x {\n  a = 1 + 2\n  # absorbed\n  b = 3\n}\n",
            options=self._OPTIONS,
        )
        block = actual["x"][0]
        self.assertIn({"value": "absorbed"}, block["__comments__"])
        self.assertNotIn("__inline_comments__", block)

    def test_inline_after_binary_op(self):
        actual = _parse_and_serialize(
            "x {\n  a = 1 + 2 # inline\n  b = 3\n}\n",
            options=self._OPTIONS,
        )
        block = actual["x"][0]
        self.assertEqual(block["__inline_comments__"], [{"value": "inline"}])

    def test_comment_inside_object(self):
        actual = _parse_and_serialize(
            "x {\n  m = {\n    # inside\n    k = 1\n  }\n}\n",
            options=self._OPTIONS,
        )
        block = actual["x"][0]
        self.assertEqual(block["__inline_comments__"], [{"value": "inside"}])
        self.assertNotIn("__comments__", block)

    def test_multiline_block_comment(self):
        actual = _parse_and_serialize(
            "x {\n  /*\n  multi\n  line\n  */\n  a = 1\n}\n",
            options=self._OPTIONS,
        )
        block = actual["x"][0]
        self.assertEqual(block["__comments__"], [{"value": "multi\n  line"}])

    def test_no_comments_without_option(self):
        actual = _parse_and_serialize(
            "// comment\nx = 1\n",
            options=SerializationOptions(with_comments=False),
        )
        self.assertNotIn("__comments__", actual)
        self.assertNotIn("__inline_comments__", actual)


class TestHeredocs(TestCase):
    """Test heredoc serialization, flattening, restoration, and round-trips.

    Scenarios:
    1. HCL with heredocs → JSON (preserve_heredocs=True)
    2. HCL with heredocs → JSON (preserve_heredocs=False, newlines escaped)
    3. Flattened JSON → HCL (strings_to_heredocs=True restores multiline)
    4. Full round-trip: flatten → restore → reparse → reflatten matches
    """

    maxDiff = None
    _FLATTEN_OPTIONS = SerializationOptions(preserve_heredocs=False)

    def _load_special(self, name, suffix):
        return (SPECIAL_DIR / f"{name}{suffix}").read_text()

    def test_parse_preserves_heredocs(self):
        """HCL → JSON with default options preserves heredoc markers."""
        hcl_text = self._load_special("heredocs", ".tf")
        actual = _parse_and_serialize(hcl_text)
        expected = json.loads(self._load_special("heredocs_preserved", ".json"))
        self.assertEqual(actual, expected)

    def test_parse_flattens_heredocs(self):
        """HCL → JSON with preserve_heredocs=False escapes newlines in quoted strings."""
        hcl_text = self._load_special("heredocs", ".tf")
        actual = _parse_and_serialize(hcl_text, options=self._FLATTEN_OPTIONS)
        expected = json.loads(self._load_special("heredocs_flattened", ".json"))
        self.assertEqual(actual, expected)

    def test_flattened_to_hcl_restores_heredocs(self):
        """Flattened JSON → HCL with strings_to_heredocs=True restores multiline heredocs."""
        flattened = json.loads(self._load_special("heredocs_flattened", ".json"))
        d_opts = DeserializerOptions(strings_to_heredocs=True)
        actual = _deserialize_and_reconstruct_with_options(flattened, d_opts)
        expected = self._load_special("heredocs_restored", ".tf")
        self.assertMultiLineEqual(actual, expected)

    def test_flatten_restore_round_trip(self):
        """Flatten → restore → reparse → reflatten produces identical flattened JSON."""
        hcl_text = self._load_special("heredocs", ".tf")

        # Forward: HCL → flattened JSON
        flattened = _parse_and_serialize(hcl_text, options=self._FLATTEN_OPTIONS)

        # Restore: flattened JSON → HCL with heredocs
        d_opts = DeserializerOptions(strings_to_heredocs=True)
        restored_hcl = _deserialize_and_reconstruct_with_options(flattened, d_opts)

        # Reflatten: restored HCL → flattened JSON
        reflattened = _parse_and_serialize(restored_hcl, options=self._FLATTEN_OPTIONS)

        self.assertEqual(
            reflattened,
            flattened,
            "Flatten → restore → reflatten did not produce identical JSON",
        )
