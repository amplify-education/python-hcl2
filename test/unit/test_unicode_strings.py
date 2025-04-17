"""Test building HCL files with complex float values"""

from pathlib import Path
from unittest import TestCase

import hcl2
import hcl2.builder


HELPERS_DIR = Path(__file__).absolute().parent.parent / "helpers"
HCL2_DIR = HELPERS_DIR / "terraform-config"
JSON_DIR = HELPERS_DIR / "terraform-config-json"
HCL2_FILES = [str(file.relative_to(HCL2_DIR)) for file in HCL2_DIR.iterdir()]


class TestUnicodeStrings(TestCase):
    """Test building hcl files with various float representations"""

    # print any differences fully to the console
    maxDiff = None

    def test_builder_with_complex_floats(self):
        builder = hcl2.Builder()

        builder.block(
            "locals",
            basic_unicode = "Hello, 世界! こんにちは Привет नमस्ते",
            unicode_escapes = "© ♥ ♪ ☠ ☺",
            emoji_string = "🚀 🌍 🔥 🎉",
            rtl_text = "English and العربية text mixed",
            complex_unicode = "Python (파이썬) es 很棒的! ♥ αβγδ",
            ascii="ASCII: abc123",
            emoji="Emoji: 🚀🌍🔥🎉",
            math="Math: ∑∫√∞≠≤≥",
            currency="Currency: £€¥₹₽₩",
            arrows="Arrows: ←↑→↓↔↕",
            cjk="CJK: 你好世界안녕하세요こんにちは",
            cyrillic="Cyrillic: Привет мир",
            special="Special: ©®™§¶†‡",
            mixed_content=(
                "<<-EOT\n"
                "    Line with interpolation: ${var.name}\n"
                "    Line with emoji: 👨‍👩‍👧‍👦\n"
                '    Line with quotes: "quoted text"\n'
                "    Line with backslash: \\escaped\n"
                "  EOT"
            )
        )

        self.compare_filenames(builder, "unicode_strings.tf")

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
