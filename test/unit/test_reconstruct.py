""" Test reconstructing hcl files"""

import json
from pathlib import Path
from unittest import TestCase

import hcl2


HELPERS_DIR = Path(__file__).absolute().parent.parent / "helpers"
HCL2_DIR = HELPERS_DIR / "terraform-config"
HCL2_FILES = [str(file.relative_to(HCL2_DIR)) for file in HCL2_DIR.iterdir()]
JSON_DIR = HELPERS_DIR / "terraform-config-json"


class TestReconstruct(TestCase):
    """Test reconstructing a variety of hcl files"""

    # print any differences fully to the console
    maxDiff = None

    def test_write_terraform(self):
        """Test reconstructing a set of hcl2 files, to make sure they parse to the same structure"""
        for hcl_path in HCL2_FILES:
            yield self.check_terraform, hcl_path

    def test_write_terraform_exact(self):
        """
        Test reconstructing a set of hcl2 files, to make sure they
        reconstruct exactly the same, including whitespace.
        """

        # the reconstruction process is not precise, so some files do not
        # reconstruct their whitespace exactly the same, but they are
        # syntactically equivalent. This list is a target for further
        # improvements to the whitespace handling of the reconstruction
        # algorithm.
        inexact_files = [
            # the reconstructor loses commas on the last element in an array,
            # even if they're in the input file
            "iam.tf",
            "variables.tf",
            # the reconstructor doesn't preserve indentation within comments
            # perfectly
            "multiline_expressions.tf",
            # the reconstructor doesn't preserve the line that a ternary is
            # broken on.
            "route_table.tf",
        ]

        for hcl_path in HCL2_FILES:
            if hcl_path not in inexact_files:
                yield self.check_whitespace, hcl_path

    def check_terraform(self, hcl_path_str: str):
        """
        Loads a single hcl2 file, parses it, reconstructs it,
        parses the reconstructed file, and compares with the expected json
        """
        hcl_path = (HCL2_DIR / hcl_path_str).absolute()
        json_path = JSON_DIR / hcl_path.relative_to(HCL2_DIR).with_suffix(".json")
        with hcl_path.open("r") as hcl_file, json_path.open("r") as json_file:
            hcl_file_content = hcl_file.read()
            try:
                hcl_ast = hcl2.parses(hcl_file_content)
            except Exception as exc:
                assert False, f"failed to tokenize terraform in `{hcl_path_str}`: {exc}"

            try:
                hcl_reconstructed = hcl2.writes(hcl_ast)
            except Exception as exc:
                assert (
                    False
                ), f"failed to reconstruct terraform in `{hcl_path_str}`: {exc}"

            try:
                hcl2_dict = hcl2.loads(hcl_reconstructed)
            except Exception as exc:
                assert (
                    False
                ), f"failed to tokenize terraform in file reconstructed from `{hcl_path_str}`: {exc}"

            json_dict = json.load(json_file)
            self.assertDictEqual(
                hcl2_dict,
                json_dict,
                f"failed comparing {hcl_path_str} with reconstructed version",
            )

    def check_whitespace(self, hcl_path_str: str):
        """Tests that the reconstructed file matches the original file exactly."""
        hcl_path = (HCL2_DIR / hcl_path_str).absolute()
        with hcl_path.open("r") as hcl_file:
            hcl_file_content = hcl_file.read()
            try:
                hcl_ast = hcl2.parses(hcl_file_content)
            except Exception as exc:
                assert False, f"failed to tokenize terraform in `{hcl_path_str}`: {exc}"

            try:
                hcl_reconstructed = hcl2.writes(hcl_ast)
            except Exception as exc:
                assert (
                    False
                ), f"failed to reconstruct terraform in `{hcl_path_str}`: {exc}"

            self.assertMultiLineEqual(
                hcl_reconstructed,
                hcl_file_content,
                f"file {hcl_path_str} does not match its reconstructed version \
                    exactly. this is usually whitespace related.",
            )
