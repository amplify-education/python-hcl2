"""A parser for HCL2 implemented using the Lark parser"""
import os
from os.path import dirname

from lark import Lark

from hcl2.transformer import DictTransformer

PARSER_FILE = os.path.join(dirname(__file__), '.lark_cache.bin')

hcl2 = Lark.open(
    'hcl2.lark',
    parser='lalr',
    cache=PARSER_FILE,  # Disable/Delete file to effect changes to the grammar
    rel_to=__file__,
    transformer=DictTransformer()
)
