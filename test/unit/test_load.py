""" Test parsing a variety of hcl files"""
import os
from os.path import dirname
from unittest import TestCase

import hcl2
from hcl2.parser import PARSER_FILE, create_parser_file


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
            for file in files:
                file_path = os.path.join(current_dir, file)

                with self.subTest(msg=file_path):
                    with open(file_path, 'r') as file2:
                        hcl2.load(file2)
