"""A parser for HCL2 implemented using the Lark parser"""
import functools
from pathlib import Path

from lark import Lark

from hcl2.postlexer import PostLexer


PARSER_FILE = Path(__file__).absolute().resolve().parent / ".lark_cache.bin"


@functools.lru_cache()
def parser() -> Lark:
    """Build standard parser for transforming HCL2 text into python structures"""
    return Lark.open(
        "hcl2.lark",
        parser="lalr",
        cache=str(PARSER_FILE),  # Disable/Delete file to effect changes to the grammar
        rel_to=__file__,
        propagate_positions=True,
        postlex=PostLexer(),
    )
