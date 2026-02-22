"""Round-trip tests for the HCL2 → JSON → HCL2 pipeline.

Every test starts from the source HCL files in test/integration/hcl2_original/
and runs the pipeline forward from there, comparing actuals against expected
outputs at each stage:

1. HCL → JSON serialization (parse + transform + serialize)
2. JSON → JSON reserialization (serialize + deserialize + reserialize)
3. JSON → HCL reconstruction (serialize + deserialize + format + reconstruct)
4. Full round-trip (HCL → JSON → HCL → JSON produces identical JSON)
"""

import json
from enum import Enum
from pathlib import Path
from typing import List
from unittest import TestCase

from hcl2.api import parses_to_tree
from hcl2.deserializer import BaseDeserializer
from hcl2.formatter import BaseFormatter
from hcl2.reconstructor import HCLReconstructor
from hcl2.transformer import RuleTransformer

INTEGRATION_DIR = Path(__file__).absolute().parent
HCL2_ORIGINAL_DIR = INTEGRATION_DIR / "hcl2_original"

_STEP_DIRS = {
    "hcl2_original": HCL2_ORIGINAL_DIR,
    "hcl2_reconstructed": INTEGRATION_DIR / "hcl2_reconstructed",
    "json_serialized": INTEGRATION_DIR / "json_serialized",
    "json_reserialized": INTEGRATION_DIR / "json_reserialized",
}

_STEP_SUFFIXES = {
    "hcl2_original": ".tf",
    "hcl2_reconstructed": ".tf",
    "json_serialized": ".json",
    "json_reserialized": ".json",
}


class SuiteStep(Enum):
    ORIGINAL = "hcl2_original"
    RECONSTRUCTED = "hcl2_reconstructed"
    JSON_SERIALIZED = "json_serialized"
    JSON_RESERIALIZED = "json_reserialized"


def _get_suites() -> List[str]:
    """
    Get a list of the test suites.
    Names of a test suite is a name of file in `test/integration/hcl2_original/` without the .tf suffix.

    Override SUITES to run a specific subset, e.g. SUITES = ["config"]
    """
    return SUITES or sorted(
        file.stem for file in HCL2_ORIGINAL_DIR.iterdir() if file.is_file()
    )


# set this to arbitrary list of test suites to run,
#   e.g. `SUITES = ["smoke"]` to run the tests only for `test/integration/hcl2_original/smoke.tf`
SUITES: List[str] = []


def _get_suite_file(suite_name: str, step: SuiteStep) -> Path:
    """Return the path for a given suite name and pipeline step."""
    return _STEP_DIRS[step.value] / (suite_name + _STEP_SUFFIXES[step.value])


def _parse_and_serialize(hcl_text: str, options=None) -> dict:
    """Parse HCL text and serialize to a Python dict."""
    parsed_tree = parses_to_tree(hcl_text)
    rules = RuleTransformer().transform(parsed_tree)
    if options:
        return rules.serialize(options=options)
    return rules.serialize()


def _deserialize_and_reserialize(serialized: dict) -> dict:
    """Deserialize a Python dict back through the rule tree and reserialize."""
    deserializer = BaseDeserializer()
    formatter = BaseFormatter()
    deserialized = deserializer.load_python(serialized)
    formatter.format_tree(deserialized)
    return deserialized.serialize()


def _deserialize_and_reconstruct(serialized: dict) -> str:
    """Deserialize a Python dict and reconstruct HCL text."""
    deserializer = BaseDeserializer()
    formatter = BaseFormatter()
    reconstructor = HCLReconstructor()
    deserialized = deserializer.load_python(serialized)
    formatter.format_tree(deserialized)
    lark_tree = deserialized.to_lark()
    return reconstructor.reconstruct(lark_tree)


class TestRoundTripSerialization(TestCase):
    """Test HCL2 → JSON serialization: parse HCL, transform, serialize, compare with expected JSON."""

    maxDiff = None

    def test_hcl_to_json(self):
        for suite in _get_suites():
            with self.subTest(suite=suite):
                hcl_path = _get_suite_file(suite, SuiteStep.ORIGINAL)
                json_path = _get_suite_file(suite, SuiteStep.JSON_SERIALIZED)

                actual = _parse_and_serialize(hcl_path.read_text())
                expected = json.loads(json_path.read_text())

                self.assertEqual(
                    actual,
                    expected,
                    f"HCL → JSON serialization mismatch for {suite}",
                )


class TestRoundTripReserialization(TestCase):
    """Test JSON → JSON reserialization: parse HCL, serialize, deserialize, reserialize, compare with expected."""

    maxDiff = None

    def test_json_reserialization(self):
        for suite in _get_suites():
            with self.subTest(suite=suite):
                hcl_path = _get_suite_file(suite, SuiteStep.ORIGINAL)
                json_reserialized_path = _get_suite_file(suite, SuiteStep.JSON_RESERIALIZED)

                serialized = _parse_and_serialize(hcl_path.read_text())
                actual = _deserialize_and_reserialize(serialized)

                expected = json.loads(json_reserialized_path.read_text())
                self.assertEqual(
                    actual,
                    expected,
                    f"JSON reserialization mismatch for {suite}",
                )


class TestRoundTripReconstruction(TestCase):
    """Test JSON → HCL reconstruction: parse HCL, serialize, deserialize, format, reconstruct, compare with expected HCL."""

    maxDiff = None

    def test_json_to_hcl(self):
        for suite in _get_suites():
            with self.subTest(suite=suite):
                hcl_path = _get_suite_file(suite, SuiteStep.ORIGINAL)
                hcl_reconstructed_path = _get_suite_file(suite, SuiteStep.RECONSTRUCTED)

                serialized = _parse_and_serialize(hcl_path.read_text())
                actual = _deserialize_and_reconstruct(serialized)

                expected = hcl_reconstructed_path.read_text()
                self.assertMultiLineEqual(
                    actual,
                    expected,
                    f"HCL reconstruction mismatch for {suite}",
                )


class TestRoundTripFull(TestCase):
    """Test full round-trip: HCL → JSON → HCL → JSON should produce matching JSON."""

    maxDiff = None

    def test_full_round_trip(self):
        for suite in _get_suites():
            with self.subTest(suite=suite):
                hcl_path = _get_suite_file(suite, SuiteStep.ORIGINAL)
                original_hcl = hcl_path.read_text()

                # Forward: HCL → JSON
                serialized = _parse_and_serialize(original_hcl)

                # Reconstruct: JSON → HCL
                reconstructed_hcl = _deserialize_and_reconstruct(serialized)

                # Reparse: reconstructed HCL → JSON
                reserialized = _parse_and_serialize(reconstructed_hcl)

                self.assertEqual(
                    reserialized,
                    serialized,
                    f"Full round-trip mismatch for {suite}: "
                    f"HCL → JSON → HCL → JSON did not produce identical JSON",
                )
