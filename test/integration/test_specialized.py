"""Specialized integration tests for specific features and scenarios.

Unlike the suite-based round-trip tests, these target individual features
(operator precedence, Builder round-trip) with dedicated golden files
in test/integration/special/.
"""

import json
from pathlib import Path
from unittest import TestCase

from hcl2.utils import SerializationOptions

from test.integration.test_round_trip import (
    _parse_and_serialize,
    _deserialize_and_reserialize,
    _deserialize_and_reconstruct,
)

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
