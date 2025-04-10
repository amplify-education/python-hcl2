# pylint:disable=C0116

"""Test building an HCL file from scratch"""

from pathlib import Path
from unittest import TestCase

import hcl2
import hcl2.builder


HELPERS_DIR = Path(__file__).absolute().parent.parent / "helpers"
HCL2_DIR = HELPERS_DIR / "terraform-config"
JSON_DIR = HELPERS_DIR / "terraform-config-json"
HCL2_FILES = [str(file.relative_to(HCL2_DIR)) for file in HCL2_DIR.iterdir()]


class TestBuilder(TestCase):
    """Test building a variety of hcl files"""

    # print any differences fully to the console
    maxDiff = None

    def test_build_blocks_tf(self):
        nested_builder = hcl2.Builder()
        nested_builder.block("nested_block_1", ["a"], foo="bar")
        nested_builder.block("nested_block_1", ["a", "b"], bar="foo")
        nested_builder.block("nested_block_1", foobar="barfoo")
        nested_builder.block("nested_block_2", barfoo="foobar")

        builder = hcl2.Builder()
        builder.block("block", a=1)
        builder.block("block", ["label"], __nested_builder__=nested_builder, b=2)

        self.compare_filenames(builder, "blocks.tf")

    def test_build_escapes_tf(self):
        builder = hcl2.Builder()

        builder.block("block", ["block_with_newlines"], a="line1\nline2")

        self.compare_filenames(builder, "escapes.tf")

    def test_locals_embdedded_condition_tf(self):
        builder = hcl2.Builder()

        builder.block(
            "locals",
            terraform={
                "channels": "${(local.running_in_ci ? local.ci_channels : local.local_channels)}",
                "authentication": [],
                "foo": None,
            },
        )

        self.compare_filenames(builder, "locals_embedded_condition.tf")

    def test_locals_embedded_function_tf(self):
        builder = hcl2.Builder()

        function_test = (
            "${var.basename}-${var.forwarder_function_name}_"
            '${md5("${var.vpc_id}${data.aws_region.current.name}")}'
        )
        builder.block("locals", function_test=function_test)

        self.compare_filenames(builder, "locals_embedded_function.tf")

    def test_locals_embedded_interpolation_tf(self):
        builder = hcl2.Builder()

        attributes = {
            "simple_interpolation": "prefix:${var.foo}-suffix",
            "embedded_interpolation": "(long substring without interpolation); "
            '${module.special_constants.aws_accounts["aaa-${local.foo}-${local.bar}"]}/us-west-2/key_foo',
            "escaped_interpolation": "prefix:$${aws:username}-suffix",
        }

        builder.block("locals", **attributes)

        self.compare_filenames(builder, "string_interpolations.tf")

    def test_provider_function_tf(self):
        builder = hcl2.Builder()

        builder.block(
            "locals",
            name2='${provider::test2::test("a")}',
            name3='${test("a")}',
        )

        self.compare_filenames(builder, "provider_function.tf")

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
