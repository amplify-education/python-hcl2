"""A reconstructor for HCL2 implemented using Lark's experimental reconstruction functionality"""

import re
import json
from typing import List, Dict, Callable, Optional

from lark import Lark, Tree
from lark.grammar import Terminal, NonTerminal, Symbol
from lark.lexer import Token, PatternStr, TerminalDef
from lark.reconstruct import Reconstructor, is_iter_empty
from lark.tree_matcher import is_discarded_terminal
from lark.utils import is_id_continue
from lark.visitors import Transformer_InPlace

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

# TODO: remove these character sets
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

KEYWORDS = [
    Terminal("IF"),
    Terminal("IN"),
    Terminal("FOR"),
    Terminal("FOR_EACH"),
]

# space on both sides, generally
BINARY_OPS = [
    Terminal("QMARK"),
    Terminal("BINARY_OP"),
    Terminal("ASSIGN"),
]


# function to remove the backslashes within interpolated portions
def reverse_quotes_within_interpolation(s: str) -> str:
    """
    A common operation is to `json.dumps(s)` where s is a string to output in
    Terraform. This is useful for automatically escaping any quotes within the
    string, but this escapes quotes within interpolation incorrectly. This
    method removes any erroneous escapes within interpolated segments of a
    string.
    """
    return re.sub(r"\$\{(.*)\}", lambda m: m.group(0).replace('\\"', '"'), s)


def _add_extra_space(prev_item, item):
    # TODO: remove this function once all rules are ported
    return False

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

# TODO: remove this function after its logic is incorporated into the transformer
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


class WriteTokensAndMetaTransformer(Transformer_InPlace):
    """
    Inserts discarded tokens into their correct place, according to the
    rules of grammar, and annotates with metadata during reassembly.

    This is a modification of lark.reconstruct.WriteTokensTransformer
    """

    tokens: Dict[str, TerminalDef]
    term_subs: Dict[str, Callable[[Symbol], str]]

    def __init__(
        self,
        tokens: Dict[str, TerminalDef],
        term_subs: Dict[str, Callable[[Symbol], str]],
    ) -> None:
        self.tokens = tokens
        self.term_subs = term_subs

    def __default__(self, data, children, meta):
        if not getattr(meta, "match_tree", False):
            return Tree(data, children)
        iter_args = iter(
            [child[2] if isinstance(child, tuple) else child for child in children]
        )
        to_write = []
        for sym in meta.orig_expansion:
            if is_discarded_terminal(sym):
                try:
                    v = self.term_subs[sym.name](sym)
                except KeyError:
                    t = self.tokens[sym.name]
                    if not isinstance(t.pattern, PatternStr):
                        raise NotImplementedError(
                            "Reconstructing regexps not supported yet: %s" % t
                        )

                    v = t.pattern.value

                # annotate the leaf with the specific rule (data) and terminal
                # (sym) it was generated from
                to_write.append((data, sym, v))
            else:
                x = next(iter_args)
                if isinstance(x, list):
                    to_write += x
                else:
                    if isinstance(x, Token):
                        assert Terminal(x.type) == sym, x
                        # annotate the leaf with the specific rule (data) and
                        # terminal (sym) it was generated from
                        to_write.append((data, sym, x))
                    else:
                        assert NonTerminal(x.data) == sym, (sym, x)
                        to_write.append(x)

        assert is_iter_empty(iter_args)
        return to_write


class HCLReconstructor(Reconstructor):
    """This class converts a Lark.Tree AST back into a string representing the underlying HCL code."""

    # these variables track state during reconstuction to enable us to make
    # informed decisions about formatting our output.
    #
    # TODO: it's likely that we could do away with a lot of this tracking if we
    # stored the nonterminal (rule) that each token was generated from... this
    # is a project for later.
    last_char_space = True
    last_terminal = None
    deferred_item = None

    def __init__(
        self,
        parser: Lark,
        term_subs: Optional[Dict[str, Callable[[Symbol], str]]] = None,
    ):
        Reconstructor.__init__(self, parser, term_subs)

        self.write_tokens = WriteTokensAndMetaTransformer(
            {t.name: t for t in self.tokens}, term_subs or {}
        )

    def _should_add_space(self, rule, current_terminal):
        # we don't need to add multiple spaces
        if self.last_char_space:
            return False

        # we don't add a space at the start of the file
        if not self.last_terminal:
            return False

        # these terminals always have a space after them
        if (
            self.last_terminal
            in [
                Terminal("EQ"),
                Terminal("COMMA"),
            ]
            + KEYWORDS
            + BINARY_OPS
        ):
            return True

        # if we're in a ternary
        if isinstance(rule, Token) and rule.value == "conditional":

            # always add space before and after the colon
            if self.last_terminal == Terminal("COLON") or current_terminal == Terminal(
                "COLON"
            ):
                return True

        # if we're in a block
        if (isinstance(rule, Token) and rule.value == "block") or (
            isinstance(rule, str) and re.match(r"^__block_(star|plus)_.*", rule)
        ):
            # always add space before the starting brace
            if current_terminal == Terminal("LBRACE"):
                return True

            # always add space before the closing brace
            if current_terminal == Terminal(
                "RBRACE"
            ) and self.last_terminal != Terminal("LBRACE"):
                return True

            # always add space between string literals
            if current_terminal == Terminal("STRING_LIT"):
                return True

        # if (
        #     self.last_terminal == Terminal("NAME")
        #     and current_terminal
        #     in [
        #         # these terminals have a space before them if they come after a "NAME" terminal
        #         Terminal("LBRACE"),
        #         Terminal("STRING_LIT"),
        #     ]
        #     + KEYWORDS
        #     + BINARY_OPS
        # ):
        #     return True

        # TODO: remove these and replace with "rule aware" handling
        if self.last_terminal == Terminal("COMMA") and current_terminal in [
            # these terminals have a space before them if they come after a "COMMA" terminal
            Terminal("STRING_LIT"),
            Terminal("DECIMAL"),
        ]:
            return True

        if self.last_terminal == Terminal("STRING_LIT") and current_terminal in [
            # these terminals have a space before them if they come after a "STRING_LIT" terminal
            Terminal("LBRACE"),
            Terminal("STRING_LIT"),
            Terminal("QMARK"),
        ]:
            return True

        if self.last_terminal == Terminal("LBRACE") and current_terminal in [
            # these terminals have a space before them if they come after a "LBRACE" terminal
            Terminal("NAME")
        ]:
            return True

        # these terminals get space between them and binary ops
        if (
            self.last_terminal
            in [
                Terminal("RSQB"),
                Terminal("RPAR"),
            ]
            and current_terminal in KEYWORDS + BINARY_OPS
        ):
            return True

        # the catch-all case, we're not sure, so don't add a space
        return False

    def _reconstruct(self, tree):
        unreduced_tree = self.match_tree(tree, tree.data)
        res = self.write_tokens.transform(unreduced_tree)
        for item in res:
            # any time we encounter a child tree, we recurse
            if isinstance(item, Tree):
                yield from self._reconstruct(item)

            # every leaf should be a tuple, which contains information about
            # which terminal the leaf represents
            elif isinstance(item, tuple):
                rule, terminal, value = item
                print(item)

                # first, handle any deferred items
                if self.deferred_item is not None:
                    deferred_rule, deferred_terminal, deferred_value = (
                        self.deferred_item
                    )

                    # if we deferred a comma and the next character ends a
                    # parenthesis or block, we can throw it out
                    if deferred_terminal == Terminal("COMMA") and terminal in [
                        Terminal("RPAR"),
                        Terminal("RBRACE"),
                    ]:
                        pass
                    # in any other case, we print the deferred item
                    else:
                        yield deferred_value

                        # and do our bookkeeping
                        self.last_terminal = deferred_terminal
                        if deferred_value and not deferred_value[-1].isspace():
                            self.last_char_space = False

                    # clear the deferred item
                    self.deferred_item = None

                # potentially add a space before the next token
                if self._should_add_space(rule, terminal):
                    yield " "
                    self.last_char_space = True

                # potentially defer the item if needs to be
                if terminal in [Terminal("COMMA")]:
                    self.deferred_item = item
                else:
                    # otherwise print the next token
                    yield value

                    # if we're in a ternary, we need to add a space after the colon:
                    if (
                        isinstance(rule, Token)
                        and rule.value == "conditional"
                        and terminal == Terminal("COLON")
                    ):
                        yield " "
                        self.last_char_space = True

                    # and do our bookkeeping so we can make an informed
                    # decision about formatting next time

                    self.last_terminal = terminal
                    if value:
                        self.last_char_space = value[-1].isspace()

            # otherwise, we just have a string
            else:
                raise RuntimeError(f"Unknown bare token type: {item}")
                # yield item
                # self.last_terminal = None
                # if value and not value[-1].isspace():
                #     self.last_char_space = False

    def reconstruct(self, tree):
        """Convert a Lark.Tree AST back into a string representation of HCL."""
        return Reconstructor.reconstruct(
            self,
            tree,
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

    def _NL(self, level: int, comma: bool = False) -> Tree:
        # some rules expect the `new_line_and_or_comma` token
        if comma:
            return Tree(
                Token("RULE", "new_line_and_or_comma"),
                [self._NL(level=level, comma=False)],
            )
        # otherwise, return the `new_line_or_comment` token
        else:
            return Tree(
                Token("RULE", "new_line_or_comment"),
                [Token("NL_OR_COMMENT", f"\n{'  ' * level}")],
            )

    # rules: the value of a block is always an array of dicts,
    # the key is the block type
    def _list_is_a_block(self, v: list) -> bool:
        for obj in v:
            if not self._dict_is_a_block(obj):
                return False

        return True

    def _dict_is_a_block(self, sub_obj: any) -> bool:
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

        # if the sub object has a single string key whose value is an object,
        # it _could_ be a labeled block... but we'd have to check if the sub
        # object is a block (recurse)
        label = list(sub_obj)[0]
        sub_sub_obj = sub_obj[label]
        if self._dict_is_a_block(sub_sub_obj):
            return True

        # if the objects in the array have a single key whose child is not a
        # block, the array is just an array of objects, not a block
        return False

    def _block_has_label(self, b: dict) -> bool:
        return len(b.keys()) == 1

    def _calculate_block_labels(self, b: dict) -> List[str]:
        # if b doesn't have a label
        if len(b.keys()) != 1:
            return ([], b)

        # otherwise, find the label
        curr_label = list(b)[0]
        potential_body = b[curr_label]
        if (
            "__start_line__" in potential_body.keys()
            or "__end_line__" in potential_body.keys()
        ):
            return ([curr_label], potential_body)
        else:
            next_label, block_body = self._calculate_block_labels(potential_body)
            return ([curr_label] + next_label, block_body)

    def _name_to_identifier(self, name: str) -> Tree:
        return Tree(Token("RULE", "identifier"), [Token("NAME", name)])

    def _escape_interpolated_str(self, s: str) -> str:
        # begin by doing basic JSON string escaping, to add backslashes
        s = json.dumps(s)

        # find each interpolation within the string and remove the backslashes
        s = reverse_quotes_within_interpolation(s)
        return s

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
            identifier_name = self._name_to_identifier(k)

            # first, check whether the value is a "block"
            if isinstance(v, list) and self._list_is_a_block(v):
                for block_v in v:
                    block_labels, block_body_dict = self._calculate_block_labels(
                        block_v
                    )
                    block_label_tokens = [
                        Token("STRING_LIT", f'"{block_label}"')
                        for block_label in block_labels
                    ]
                    block_body = self._transform_dict_to_body(
                        block_body_dict, level + 1
                    )

                    # create our actual block to add to our own body
                    block = Tree(
                        Token("RULE", "block"),
                        [identifier_name] + block_label_tokens + [block_body],
                    )
                    children.append(block)
                    children.append(self._NL(level))

            # if the value isn't a block, it's an attribute
            else:
                expr_term = self._transform_value_to_expr_term(v, level)
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

    def _transform_value_to_expr_term(self, v, level) -> Token:
        """Transforms a value from a dictionary into an "expr_term" (a value in HCL2)

        Anything passed to this function is treated "naively". Any lists passed
        are assumed to be tuples, and any dicts passed are assumed to be objects.
        No more checks will be performed for either to see if they are "blocks"
        as ehis check happens in `_transform_dict_to_body`.
        """

        # for lists, recursively turn the child elements into expr_terms and
        # store within a tuple
        if isinstance(v, list):
            tuple_tree = Tree(
                Token("RULE", "tuple"),
                [self._transform_value_to_expr_term(tuple_v, level) for tuple_v in v],
            )
            return Tree(Token("RULE", "expr_term"), [tuple_tree])
        # for dicts, recursively turn the child k/v pairs into object elements
        # and store within an object
        elif isinstance(v, dict):
            elems = []
            for k, dict_v in v.items():
                if k in ["__start_line__", "__end_line__"]:
                    continue
                identifier = self._name_to_identifier(k)
                value_expr_term = self._transform_value_to_expr_term(dict_v, level)
                elems.append(
                    Tree(
                        Token("RULE", "object_elem"),
                        [identifier, Token("EQ", " ="), value_expr_term],
                    )
                )
                elems.append(self._NL(level, comma=True))
            return Tree(
                Token("RULE", "expr_term"), [Tree(Token("RULE", "object"), elems)]
            )
        # treat booleans appropriately
        elif isinstance(v, bool):
            return Tree(
                Token("RULE", "expr_term"),
                [
                    Tree(
                        Token("RULE", "identifier"),
                        [Token("NAME", "true" if v else "false")],
                    )
                ],
            )
        # store integers as literals, digit by digit
        elif isinstance(v, int):
            return Tree(
                Token("RULE", "expr_term"),
                [
                    Tree(
                        Token("RULE", "int_lit"),
                        [Token("DECIMAL", digit) for digit in str(v)],
                    )
                ],
            )
        # store strings as single literals
        elif isinstance(v, str):
            return Tree(
                Token("RULE", "expr_term"),
                [Token("STRING_LIT", self._escape_interpolated_str(v))],
            )
        else:
            raise Exception(f"Unknown type to transform {type(v)}")


hcl2_reconstructor = HCLReconstructor(hcl2)
hcl2_reverse_transformer = HCLReverseTransformer()
