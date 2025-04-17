"""Test building HCL files with complex float values"""

from pathlib import Path
from unittest import TestCase

import hcl2
import hcl2.builder


HELPERS_DIR = Path(__file__).absolute().parent.parent / "helpers"
HCL2_DIR = HELPERS_DIR / "terraform-config"
JSON_DIR = HELPERS_DIR / "terraform-config-json"
HCL2_FILES = [str(file.relative_to(HCL2_DIR)) for file in HCL2_DIR.iterdir()]


class TestComplexFloats(TestCase):
    """Test building hcl files with various float representations"""

    # print any differences fully to the console
    maxDiff = None

    def test_builder_with_complex_floats(self):
        builder = hcl2.Builder()

        builder.block(
            "resource",
            ["test_resource", "float_examples"],
            simple_float = 123.456,
            small_float = 0.123,
            large_float = 9876543.21,
            negative_float = -42.5,
            negative_small = -0.001,
            scientific_positive = builder.sci_float(1.23e5, "1.23e5"),
            scientific_negative = builder.sci_float(9.87e-3, "9.87e-3"),
            scientific_large = builder.sci_float(6.022e+23, "6.022e+23"),
            integer_as_float= 100.0,
            float_calculation = "${10.5 * 3.0 / 2.1}",
            float_comparison = "${5.6 > 2.3 ? 1.0 : 0.0}",
            float_list = [1.1, 2.2, 3.3, -4.4, builder.sci_float(5.5e2, "5.5e2")],
            float_object = {
                "pi": 3.14159,
                "euler": 2.71828,
                "sqrt2": 1.41421
            }
        )

        builder.block(
            "variable",
            ["float_variable"],
            default=3.14159,
        )

        builder.block(
            "output",
          ["float_output"],
            value="${var.float_variable * 2.0}",
        )

        self.compare_filenames(builder, "test_floats.tf")

    def compare_filenames(self, builder: hcl2.Builder, filename: str):
        hcl_dict = builder.build()
        hcl_ast = hcl2.reverse_transform(hcl_dict)
        hcl_content_built = hcl2.writes(hcl_ast)

        hcl_path = (HCL2_DIR / filename).absolute()
        with hcl_path.open("r") as hcl_file:
            hcl_file_content = hcl_file.read()
            self.assertMultiLineEqual(
                hcl_content_built,
                hcl_file_content,
                f"file {filename} does not match its programmatically built version.",
            )
