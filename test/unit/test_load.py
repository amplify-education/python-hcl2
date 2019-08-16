""" Test parsing a variety of hcl files"""
import os
from os.path import dirname
from unittest import TestCase

import hcl2


class TestLoad(TestCase):
    def setUp(self):
        self.prev_dir = os.getcwd()
        os.chdir(os.path.normpath(os.path.dirname(__file__) + '/../helpers'))

    def test_load_terraform(self):
        os.remove(os.path.join(dirname(hcl2.__file__), 'lark_parser.py'))
        for current_dir, dirs, files in os.walk("terraform-config"):
            for file in files:
                file_path = os.path.join(current_dir, file)

                with self.subTest(msg=file_path):
                    with open(file_path, 'r') as file2:
                        hcl2.load(file2.read())

    def test_load_terraform_from_cache(self):
        for current_dir, dirs, files in os.walk("terraform-config"):
            for file in files:
                file_path = os.path.join(current_dir, file)

                with self.subTest(msg=file_path):
                    with open(file_path, 'r') as file2:
                        hcl2.load(file2.read())
