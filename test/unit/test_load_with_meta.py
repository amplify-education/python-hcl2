"""Test parsing hcl files with meta parameters"""

import json
from pathlib import Path
from unittest import TestCase

import hcl2

TEST_WITH_META_DIR = Path(__file__).absolute().parent.parent / "helpers" / "with-meta"
TF_FILE_PATH = TEST_WITH_META_DIR / "data_sources.tf"
JSON_FILE_PATH = TEST_WITH_META_DIR / "data_sources.json"


class TestLoadWithMeta(TestCase):
    """Test parsing hcl files with meta parameters"""

    def test_load_terraform_meta(self):
        """Test load() with with_meta flag set to true."""
        with TF_FILE_PATH.open("r") as tf_file, JSON_FILE_PATH.open("r") as json_file:
            self.assertDictEqual(
                json.load(json_file),
                hcl2.load(tf_file, with_meta=True),
            )
