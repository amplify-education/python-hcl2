import json
import os
from os.path import dirname
from unittest import TestCase

import hcl2
from hcl2.parser import PARSER_FILE, create_parser_file, strip_line_comment_by_token


class TestParse(TestCase):
    """ Test parsing a variety of hcl files"""

    def test_strip_line_comment_by_token(self):
        test_strings = [
            ('x = "123"', 'x = "123"'),
            ('# a basic "comment', ''),
            ('x = "123" # an end of line "comment', 'x = "123" '),
            ('x = "12#3"', 'x = "12#3"'),
            ('x = "12#3" # comment', 'x = "12#3" '),
            ('x = "12#3" + "12#3" # comment', 'x = "12#3" + "12#3" '),
        ]

        for test_string, expected in test_strings:
            result = strip_line_comment_by_token(test_string, '#')
            self.assertEqual(result, expected)

        test_strings = [
            ('// a basic "comment', ''),
            ('x = "123" // an end of line "comment', 'x = "123" '),
            ('x = "12//3"', 'x = "12//3"'),
            ('x = "12//3" // comment', 'x = "12//3" '),
        ]

        for test_string, expected in test_strings:
            result = strip_line_comment_by_token(test_string, '//')
            self.assertEqual(result, expected)

    def test_parse_comments(self):
        """Test different combinations of unclosed quotes in comments. Each of these should pass parsing"""

        wrapper = """resource "aws_s3_bucket" "b" {
    bucket = "abc"
    $COMMENT
}"""

        test_strings = [
            '# a basic "comment',
            'x = "123" # an end of line "comment',
            # '# a basic "comment',
            # '# a basic "comment',
            # '# a basic "comment',
            # '# a basic "comment',
            # '# a basic "comment',
        ]

        for test_string in test_strings:
            try:
                hcl2.loads(test_string)
            except:
                self.fail(f'The parser threw an exception for the line: {test_string}')