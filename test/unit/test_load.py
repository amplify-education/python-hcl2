""" Test parsing a variety of hcl files"""
import json
import os
from os.path import dirname
from unittest import TestCase

import hcl2
from hcl2.parser import PARSER_FILE, create_parser_file

HCL2_DIR = 'terraform-config'
JSON_DIR = 'terraform-config-json'


class TestLoad(TestCase):
    """ Test parsing a variety of hcl files"""

    def setUp(self):
        self.prev_dir = os.getcwd()
        os.chdir(os.path.join(os.path.dirname(__file__), '../helpers'))

    def test_load_terraform(self):
        """Test parsing a set of hcl2 files and force recreating the parser file"""
        # delete the parser file to force it to be recreated
        os.remove(os.path.join(dirname(hcl2.__file__), PARSER_FILE))
        create_parser_file()
        self._load_test_files()

    def test_load_terraform_from_cache(self):
        """Test parsing a set of hcl2 files from a cached parser file"""
        self._load_test_files()

    def _load_test_files(self):
        """Recursively parse all files in a directory"""
        # pylint: disable=unused-variable
        for current_dir, dirs, files in os.walk("terraform-config"):
            dir_prefix = os.path.commonpath([HCL2_DIR, current_dir])
            relative_current_dir = current_dir.replace(dir_prefix, '')
            current_out_dir = os.path.join(JSON_DIR, relative_current_dir)
            for file_name in files:
                file_path = os.path.join(current_dir, file_name)
                json_file_path = os.path.join(current_out_dir, file_name)
                json_file_path = os.path.splitext(json_file_path)[0] + '.json'

                with self.subTest(msg=file_path):
                    with open(file_path, 'r') as hcl2_file, open(json_file_path, 'r') as json_file:
                        hcl2_dict = hcl2.load(hcl2_file)
                        json_dict = json.load(json_file)

                        self.assertDictEqual(hcl2_dict, json_dict)
