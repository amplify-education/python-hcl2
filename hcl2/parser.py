"""A parser for HCL2 implemented using the Lark parser"""
from pathlib import Path

from lark import Lark, Token
from lark.reconstruct import Reconstructor
from lark.utils import is_id_continue

PARSER_FILE = Path(__file__).absolute().resolve().parent / ".lark_cache.bin"


hcl2 = Lark.open(
    "hcl2.lark",
    parser="lalr",
    # Caching must be disabled to allow for reconstruction until lark-parser/lark#1472 is fixed:
    #
    #   https://github.com/lark-parser/lark/issues/1472
    #
    # cache=str(PARSER_FILE),  # Disable/Delete file to effect changes to the grammar
    rel_to=__file__,
    propagate_positions=True,
    maybe_placeholders=False,  # Needed for reconstruction
)

SPACE_AFTER = set(',+-*/~@<>="|:')
SPACE_BEFORE = (SPACE_AFTER - set(",:")) | set("'")
DIGITS = set("0123456789")
IDENT_JOINERS = set(".")

def _postprocess_reconstruct(items):
    """
    Postprocess the stream of tokens derived from the AST during reconstruction.

    For HCL2, this is used exclusively for adding whitespace in the right locations.
    """
    prev_item = ""
    for item in items:
        # see if we need to add space after the previous identifier
        if (
            prev_item
            and item
            and prev_item[-1] not in SPACE_AFTER
            and not prev_item[-1].isspace()
            and is_id_continue(prev_item[-1])
            and not item[0] in IDENT_JOINERS
            and not prev_item[-1] in DIGITS
        ):
            yield " "
            prev_item = " "

        # if the next character expects us to add a space before it
        if (
            prev_item
            and not prev_item[-1].isspace()
            and prev_item[-1] not in SPACE_AFTER
        ):
            if item[0] in SPACE_BEFORE:
                yield " "
                prev_item = " "

        # print the actual token
        yield item

        if item and item[-1] in SPACE_AFTER:
            yield " "

        # store the previous item as we continue
        prev_item = item
    yield "\n"


class HCLReconstructor:
    def __init__(self, parser):
        self._recons = Reconstructor(parser)

    def reconstruct(self, tree):
        return self._recons.reconstruct(
            tree,
            _postprocess_reconstruct,
            insert_spaces=False,
        )


hcl2_reconstructor = HCLReconstructor(hcl2)
