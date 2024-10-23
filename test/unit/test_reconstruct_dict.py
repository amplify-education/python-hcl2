""" Test reconstructing hcl files"""

import json
import traceback
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

        # the reconstruction process is not precise, so some files do not
        # reconstruct any embedded HCL expressions exactly the same. this
        # list captures those, and should be manually inspected regularly to
        # ensure that files remain syntactically equivalent
        inexact_files = [
            # one level of interpolation is stripped from this file during
            # reconstruction, since we don't have a way to distinguish it from
            # a complex HCL expression. the output parses to the same value
            # though
            "multi_level_interpolation.tf",
        ]

        for hcl_path in HCL2_FILES:
            if hcl_path not in inexact_files:
                yield self.check_terraform, hcl_path

    def check_terraform(self, hcl_path_str: str):
        """
        Loads a single hcl2 file, parses it, reconstructs it,
        parses the reconstructed file, and compares with the expected json
        """
        hcl_path = (HCL2_DIR / hcl_path_str).absolute()
        json_path = JSON_DIR / hcl_path.relative_to(HCL2_DIR).with_suffix(".json")
        with hcl_path.open("r") as hcl_file, json_path.open("r") as json_file:
            try:
                hcl2_dict_correct = hcl2.load(hcl_file)
            except Exception as exc:
                assert (
                    False
                ), f"failed to tokenize 'correct' terraform in `{hcl_path_str}`: {traceback.format_exc()}"

            json_dict = json.load(json_file)

            try:
                hcl_ast = hcl2.reverse_transform(json_dict)
            except Exception as exc:
                assert (
                    False
                ), f"failed to reverse transform HCL from `{json_path.name}`: {traceback.format_exc()}"

            try:
                hcl_reconstructed = hcl2.writes(hcl_ast)
            except Exception as exc:
                assert (
                    False
                ), f"failed to reconstruct terraform from AST from `{json_path.name}`: {traceback.format_exc()}"

            try:
                hcl2_dict_reconstructed = hcl2.loads(hcl_reconstructed)
            except Exception as exc:
                assert (
                    False
                ), f"failed to tokenize 'reconstructed' terraform from AST from `{json_path.name}`: {exc},\n{hcl_reconstructed}"

            self.assertDictEqual(
                hcl2_dict_reconstructed,
                hcl2_dict_correct,
                f"failed comparing {hcl_path_str} with reconstructed version from {json_path.name}",
            )
