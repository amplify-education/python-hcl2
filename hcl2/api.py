"""The API that will be exposed to users of this package"""
from typing import TextIO

from hcl2.parser import hcl2


def load(file: TextIO) -> dict:
    """Load a HCL2 file"""
    return loads(file.read())


def loads(text: str) -> dict:
    """Load HCL2 from a string"""
    # append new line as a workaround for https://github.com/lark-parser/lark/issues/237
    # Lark doesn't support a EOF token so our grammar can't look for "new line or end of file"
    # This means that all blocks must end in a new line even if the file ends
    # Append a new line as a temporary fix
    return hcl2.parse(text + "\n")
