"""A parser for HCL2 implemented using the Lark parser"""
from pathlib import Path

from lark import Lark
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
SPACE_BEFORE = (SPACE_AFTER - set(",:=")) | set("'")
DIGITS = set("0123456789")
IDENT_JOINERS = set(".")

def _postprocess_reconstruct(items):
    """
    Postprocess the stream of tokens derived from the AST during reconstruction.

    For HCL2, this is used exclusively for adding whitespace in the right locations.
    """
    prev_item = ""
    for item in items:
        # these rules apply if we need to add space
        if (
            prev_item  # make sure a previous item exists
            and item  # and that the current item isn't empty
            # if the last character of the previous item is a space, we abort
            and not prev_item[-1].isspace()
            # if the previous character was a number we don't want to break up
            # a numeric literal, abort
            and not prev_item[-1] in DIGITS
            # if the next item has a space at the beginning, we don't need to
            # add one, abort
            and not item[0].isspace()
            # now the scenarios when we do not abort are
            and (
                # scenario 1, the prev token ended with an identifier character
                # and the next character is not an "IDENT_JOINER" character
                (is_id_continue(prev_item[-1]) and not item[0] in IDENT_JOINERS)
                # scenario 2, the prev token ended with a character that should
                # be followed by a space
                or (prev_item[-1] in SPACE_AFTER)
                # scenario 3, the next token begins with a character that needs
                # a space preceeding it
                or (item[0] in SPACE_BEFORE)
            )
        ):
            yield " "

        # print the actual token, and store it for the next iteraction
        yield item
        prev_item = item

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
