"""Allows to get version of `lark` library in numeric form"""

from lark import __version__ as lark_version_str

lark_version = tuple(int(el) for el in lark_version_str.split("."))
