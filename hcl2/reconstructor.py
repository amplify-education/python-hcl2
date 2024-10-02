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


def _postprocess_reconstruct(items):
    """
    Postprocess the stream of tokens derived from the AST during reconstruction.

    For HCL2, this is used exclusively for adding whitespace in the right locations.
    """
    prev_item = ""
    for item in items:
        # first, handle any deferred tokens
        if type(prev_item) == tuple and prev_item[0] == "_deferred":
            prev_item = prev_item[1]

            # if the deferred token was a comma, see if we're ending a block
            if prev_item == ",":
                if item[0] not in NEVER_COMMA_BEFORE:
                    yield prev_item
            else:
                yield prev_item

        # these rules apply if we need to add space prior to the current token
        if (
            prev_item  # make sure a previous item exists
            and item  # and that the current item isn't empty
            # if the last character of the previous item is a space, we abort
            and not prev_item[-1].isspace()
            # if the previous character was a number and the next character is
            # a number. we don't want to break up a numeric literal, abort
            and not (prev_item[-1] in DIGITS and item[0] in DIGITS)
            # if the next item has a space at the beginning, we don't need to
            # add one, abort
            and not item[0].isspace()
            # if the previous character should not have a space after it, abort
            and not prev_item[-1] in NEVER_SPACE_AFTER
            # if the next character should not have a space before it, abort
            and not item[0] in NEVER_SPACE_BEFORE
            # double colons do not get space as they're part of a call to a
            # namespaced function
            and not (item == "::" or prev_item == "::")
            # if both the last character and the next character are
            # IDENT_NO_SPACE characters, we don't want a space between them either
            and not (prev_item[-1] in IDENT_NO_SPACE and item[0] in IDENT_NO_SPACE)
            # now the scenarios when we do not abort are
            and (
                # scenario 1, the prev token ended with an identifier character
                # and the next character is not an "IDENT_NO_SPACE" character
                (is_id_continue(prev_item[-1]) and not item[0] in IDENT_NO_SPACE)
                # scenario 2, the prev token ended with a character that should
                # be followed by a space
                or (
                    prev_item[-1] in CHAR_SPACE_AFTER
                    or prev_item in KEYWORDS_SPACE_AFTER
                )
                # scenario 3, the next token begins with a character that needs
                # a space preceeding it
                or (item[0] in CHAR_SPACE_BEFORE or item in KEYWORDS_SPACE_BEFORE)
                # scenario 4, the previous token was a block opening brace and
                # the next token is not a closing brace (so the block is on one
                # line and not empty)
                or (prev_item[-1] == "{" and item[0] != "}")
            )
        ):
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
    if type(prev_item) == tuple and prev_item[0] == "_deferred":
        yield prev_item[1]


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
