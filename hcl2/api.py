"""The API that will be exposed to users of this package"""
from typing import TextIO

from hcl2.parser import hcl2


def load(file: TextIO) -> dict:
    """Load a HCL2 file"""
    return hcl2.parse(file.read())


def loads(text: str) -> dict:
    """Load HCL2 from a string"""
    return hcl2.parse(text)
