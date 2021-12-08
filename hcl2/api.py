"""The API that will be exposed to users of this package"""
import re
from typing import TextIO

from hcl2.parser import hcl2, strip_line_comment


def load(file: TextIO) -> dict:
    """Load a HCL2 file"""
    return loads(file.read())


def loads(text: str) -> dict:
    """Load HCL2 from a string"""
    # append new line as a workaround for https://github.com/lark-parser/lark/issues/237
    # Lark doesn't support a EOF token so our grammar can't look for "new line or end of file"
    # This means that all blocks must end in a new line even if the file ends
    # Append a new line as a temporary fix

    # Avoid catastrophic backtracking on missing quote marks
    multi_line_string_denominator = ""

    # this will be a mostly-complete multi-line comment approach.
    # It will pick up lines that include a comment start (/*),
    # and it will check whether the comment ends on the same line.
    # But it will not handle weird things like code that
    # starts on the same line after closing a multi line comment:
    # a = 123 /* ....      <- this will get checked
    # ....
    # ... /* a = 123     <- this will not
    in_multi_line_comment = False
    found_multi_line_comment_start = False

    for line in text.split('\n'):
        token = None
        comment = None
        if not multi_line_string_denominator and \
                not in_multi_line_comment and '/*' in line:
            line, token, comment = strip_line_comment(line)
            if token == '/*':
                # handle a comment that includes a /* (e.g., `... # ... /*`
                # which is not a multi-line comment
                # first we will complete this loop and consider any part of the line that still remains
                found_multi_line_comment_start = True
        elif not multi_line_string_denominator and in_multi_line_comment and '*/' in line:
            in_multi_line_comment = False
            continue

        if not in_multi_line_comment and '= <<' in line:
            multi_line_string_denominator = line.split('= <<')[1]
        elif not in_multi_line_comment and multi_line_string_denominator \
                and re.match(rf'\s*{multi_line_string_denominator}', line):
            multi_line_string_denominator = ""
        elif not in_multi_line_comment and multi_line_string_denominator == "" \
                and line.replace('\\"', '').count('"') % 2 != 0:
            # it's possible that the unclosed quote is in a comment, so double check
            # (but we don't want to do this for every line if it's not necessary)
            stripped = strip_line_comment(line)[0] if not comment else line  # maybe we already stripped it
            if stripped.replace('\\"', '').count('"') % 2 != 0:
                # the stripped off comment is still an unclosed string, so now we have a real error
                raise ValueError(f"Line has unclosed quote marks: {line}")

        if found_multi_line_comment_start:
            found_multi_line_comment_start = False
            in_multi_line_comment = comment is not None and '*/' not in comment
            # check whether this "multiline" comment closed on the same line

    return hcl2.parse(text + "\n")
