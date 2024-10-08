"""A reconstructor for HCL2 implemented using Lark's experimental reconstruction functionality"""

from typing import List

from lark import Lark, Tree, Token
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


class HCLReverseTransformer:
    def __init__(self):
        pass

    def transform(self, d: dict) -> Tree:
        level = 0
        body = self._transform_dict_to_body(d, level)
        start = Tree(Token("RULE", "start"), [body])
        return start

    def _NL(self, level: int) -> Tree:
        return Tree(
            Token("RULE", "new_line_or_comment"),
            [Token("NL_OR_COMMENT", f"\n{'  ' * level}")],
        )

    # rules: the value of a block is always an array of dicts,
    # the key is the block type
    def _list_is_a_block(self, v: list) -> bool:
        sub_obj = v[0]

        # if the list doesn't contain dictionaries, it's not a block
        if not isinstance(sub_obj, dict):
            return False

        # if the sub object has "start_line" and "end_line" metadata,
        # the block itself is unlabeled, but it is a block
        if "__start_line__" in sub_obj.keys() or "__end_line__" in sub_obj.keys():
            return True

        # if the objects in the array have no metadata and more than 2 keys and
        # no metadata, it's just an array of objects, not a block
        if len(list(sub_obj)) != 1:
            return False

        # if the sub object has a single string key whose value is an object
        label = list(sub_obj)[0]
        sub_sub_obj = sub_obj[label]
        if not isinstance(sub_sub_obj, dict):
            return False

        # and that object has start_line and end_line metadata, the list is a
        # block, and the block is labeled by the sub object string key
        if (
            "__start_line__" in sub_sub_obj.keys()
            or "__end_line__" in sub_sub_obj.keys()
        ):
            return True

        # if the objects in the array have a single key whose child is not an
        # object, and no metadata, (or some other edge case) the array is just
        # an array of objects, not a block
        return False

    def _block_has_label(self, b: dict) -> bool:
        return len(b.keys()) == 1

    def _transform_dict_to_body(self, d: dict, level: int) -> List[Tree]:
        # we add a newline at the top of a body within a block, not the root body
        if level > 0:
            children = [self._NL(level)]
        else:
            children = []

        # iterate thru each attribute or sub-block of this block
        for k, v in d.items():
            if k in ["__start_line__", "__end_line__"]:
                continue

            # construct the identifier, whether that be a block type name or an attribute key
            identifier_name = Tree(Token("RULE", "identifier"), [Token("NAME", k)])

            # first, check whether the value is a "block"
            if isinstance(v, list) and self._list_is_a_block(v):
                for block_v in v:
                    if self._block_has_label(block_v):
                        # calculate the block label
                        block_label = list(block_v)[0]
                        block_label_token = Token("STRING_LIT", f'"{block_label}"')

                        # recursively calculate the block body
                        block_body = self._transform_dict_to_body(
                            block_v[block_label], level + 1
                        )

                        # create our actual block to add to our own body
                        block = Tree(
                            Token("RULE", "block"),
                            [identifier_name, block_label_token, block_body],
                        )
                        children.append(block)
                        children.append(self._NL(level))
                    else:
                        # recursively calculate the block body
                        block_body = self._transform_dict_to_body(block_v, level + 1)

                        # this block has no label, so just add it to our own body as is
                        block = Tree(
                            Token("RULE", "block"),
                            [identifier_name, block_body],
                        )
                        children.append(block)
                        children.append(self._NL(level))

            # if the value isn't a block, it's an attribute
            else:
                expr_term = self._transform_value_to_expr_term(v)
                attribute = Tree(
                    Token("RULE", "attribute"),
                    [identifier_name, Token("EQ", " ="), expr_term],
                )
                children.append(attribute)
                children.append(self._NL(level))

        # since we're leaving a block body here, reduce the indentation of the
        # final newline if it exists
        if (
            len(children) > 0
            and isinstance(children[-1], Tree)
            and children[-1].data.type == "RULE"
            and children[-1].data.value == "new_line_or_comment"
        ):
            children[-1] = self._NL(level - 1)

        return Tree(Token("RULE", "body"), children)

    def _transform_value_to_expr_term(self, v) -> Token:
        """Transforms a value from a dictionary into an "expr_term" (a value in HCL2)

        Anything passed to this function is treated "naively". Any lists passed
        are assumed to be tuples, and no more checks will be performed to see if
        they are "bodies" or "blocks". This check happens
        """

        if isinstance(v, list):
            # recursively turn the child elements into expr_terms and store within a tuple
            tuple_tree = Tree(
                Token("RULE", "tuple"),
                [self._transform_value_to_expr_term(tuple_v) for tuple_v in v],
            )
            return Tree(Token("RULE", "expr_term"), [tuple_tree])
        else:
            return Tree(Token("RULE", "expr_term"), [Token("STRING_LIT", f'"{v}"')])


hcl2_reconstructor = HCLReconstructor(hcl2)
hcl2_reverse_transformer = HCLReverseTransformer()
