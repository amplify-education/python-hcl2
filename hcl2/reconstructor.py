"""A reconstructor for HCL2 implemented using Lark's experimental reconstruction functionality"""

from lark import Lark
from lark.reconstruct import Reconstructor
from lark.utils import is_id_continue

# this is duplicated from `parser` because we need different options here for
# the reconstructor. please make sure changes are kept in sync between the two
# if necessary.
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

CHAR_SPACE_AFTER = set(',~@<>="|?)]:')
CHAR_SPACE_BEFORE = (CHAR_SPACE_AFTER - set(",=")) | set("'")
KEYWORDS_SPACE_AFTER = [
    "if",
    "in",
    "for",
    "for_each",
    "==",
    "!=",
    "<",
    ">",
    "<=",
    ">=",
    "-",
    "*",
    "/",
    "%",
    "&&",
    "||",
    "+",
]
KEYWORDS_SPACE_BEFORE = KEYWORDS_SPACE_AFTER
DIGITS = set("0123456789")
NEVER_SPACE_AFTER = set("[(")
NEVER_SPACE_BEFORE = set("]),.")
NEVER_COMMA_BEFORE = set("])}")
# characters that are OK to come right after an identifier with no space between
IDENT_NO_SPACE = set("()[]")


def _add_extra_space(prev_item, item):
    # pylint: disable=too-many-boolean-expressions, too-many-return-statements

    ##### the scenarios where explicitly disallow spaces: #####

    # if we already have a space, don't add another
    if prev_item[-1].isspace() or item[0].isspace():
        return False

    # none of the following should be separated by spaces:
    # - groups of digits
    # - namespaced::function::calls
    # - characters within an identifier like array[0]()
    if (
        (prev_item[-1] in DIGITS and item[0] in DIGITS)
        or item == "::"
        or prev_item == "::"
        or (prev_item[-1] in IDENT_NO_SPACE and item[0] in IDENT_NO_SPACE)
    ):
        return False

    # specific characters are also blocklisted from having spaces
    if prev_item[-1] in NEVER_SPACE_AFTER or item[0] in NEVER_SPACE_BEFORE:
        return False

    ##### the scenarios where we add spaces: #####

    # scenario 1, the prev token ended with an identifier character
    # and the next character is not an "IDENT_NO_SPACE" character
    if is_id_continue(prev_item[-1]) and not item[0] in IDENT_NO_SPACE:
        return True

    # scenario 2, the prev token or the next token should be followed by a space
    if (
        prev_item[-1] in CHAR_SPACE_AFTER
        or prev_item in KEYWORDS_SPACE_AFTER
        or item[0] in CHAR_SPACE_BEFORE
        or item in KEYWORDS_SPACE_BEFORE
    ):
        return True

    # scenario 3, the previous token was a block opening brace and
    # the next token is not a closing brace (so the block is on one
    # line and not empty)
    if prev_item[-1] == "{" and item[0] != "}":
        return True

    ##### otherwise, we don't add a space #####
    return False


def _postprocess_reconstruct(items):
    """
    Postprocess the stream of tokens derived from the AST during reconstruction.

    For HCL2, this is used exclusively for adding whitespace in the right locations.
    """
    prev_item = ""
    for item in items:
        # first, handle any deferred tokens
        if isinstance(prev_item, tuple) and prev_item[0] == "_deferred":
            prev_item = prev_item[1]

            # if the deferred token was a comma, see if we're ending a block
            if prev_item == ",":
                if item[0] not in NEVER_COMMA_BEFORE:
                    yield prev_item
            else:
                yield prev_item

        # if we're between two tokens, determine if we need to add an extra space
        # we need the previous item and the current item to exist to evaluate these rules
        if prev_item and item and _add_extra_space(prev_item, item):
            yield " "

        # in some cases, we may want to defer printing the next token
        defer_item = False

        # prevent the inclusion of extra commas if they are not intended
        if item[0] == ",":
            item = ("_deferred", item)
            defer_item = True

        # print the actual token
        if not defer_item:
            yield item

        # store the previous item for the next token
        prev_item = item

    # if the last token was deferred, print it before continuing
    if isinstance(prev_item, tuple) and prev_item[0] == "_deferred":
        yield prev_item[1]


class HCLReconstructor:
    """This class converts a Lark.Tree AST back into a string representing the underlying HCL code."""
    def __init__(self, parser):
        self._recons = Reconstructor(parser)

    def reconstruct(self, tree):
        """Convert a Lark.Tree AST back into a string representation of HCL."""
        return self._recons.reconstruct(
            tree,
            _postprocess_reconstruct,
            insert_spaces=False,
        )


hcl2_reconstructor = HCLReconstructor(hcl2)
