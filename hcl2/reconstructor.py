"""A reconstructor for HCL2 implemented using Lark's experimental reconstruction functionality"""

import re
import json
from typing import List, Dict, Callable, Optional, Union, Any, Tuple

from lark import Lark, Tree
from lark.grammar import Terminal, Symbol
from lark.lexer import Token, PatternStr, TerminalDef
from lark.reconstruct import Reconstructor
from lark.tree_matcher import is_discarded_terminal
from lark.visitors import Transformer_InPlace
from hcl2.parser import reconstruction_parser


# function to remove the backslashes within interpolated portions
def reverse_quotes_within_interpolation(interp_s: str) -> str:
    """
    A common operation is to `json.dumps(s)` where s is a string to output in
    HCL. This is useful for automatically escaping any quotes within the
    string, but this escapes quotes within interpolation incorrectly. This
    method removes any erroneous escapes within interpolated segments of a
    string.
    """
    return re.sub(r"\$\{(.*)\}", lambda m: m.group(0).replace('\\"', '"'), interp_s)


class WriteTokensAndMetaTransformer(Transformer_InPlace):
    """
    Inserts discarded tokens into their correct place, according to the rules
    of grammar, and annotates with metadata during reassembly. The metadata
    tracked here include the terminal which generated a particular string
    output, and the rule that that terminal was matched on.

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
        """
        This method is called for every token the transformer visits.
        """

        if not getattr(meta, "match_tree", False):
            return Tree(data, children)
        iter_args = iter(
            [child[2] if isinstance(child, tuple) else child for child in children]
        )
        to_write = []
        for sym in meta.orig_expansion:
            if is_discarded_terminal(sym):
                try:
                    value = self.term_subs[sym.name](sym)
                except KeyError as exc:
                    token = self.tokens[sym.name]
                    if not isinstance(token.pattern, PatternStr):
                        raise NotImplementedError(
                            f"Reconstructing regexps not supported yet: {token}"
                        ) from exc

                    value = token.pattern.value

                # annotate the leaf with the specific rule (data) and terminal
                # (sym) it was generated from
                to_write.append((data, sym, value))
            else:
                item = next(iter_args)
                if isinstance(item, list):
                    to_write += item
                else:
                    if isinstance(item, Token):
                        # annotate the leaf with the specific rule (data) and
                        # terminal (sym) it was generated from
                        to_write.append((data, sym, item))
                    else:
                        to_write.append(item)

        return to_write


class HCLReconstructor(Reconstructor):
    """This class converts a Lark.Tree AST back into a string representing the underlying HCL code."""

    # these variables track state during reconstruction to enable us to make
    # informed decisions about formatting output. They are primarily used
    # by the _should_add_space(...) method.
    last_char_space = True
    last_terminal = None
    last_rule = None
    deferred_item = None

    def __init__(
        self,
        parser: Lark,
        term_subs: Optional[Dict[str, Callable[[Symbol], str]]] = None,
    ):
        Reconstructor.__init__(self, parser, term_subs)

        self.write_tokens = WriteTokensAndMetaTransformer(
            {token.name: token for token in self.tokens}, term_subs or {}
        )

    # space around these terminals if they're within for or if statements
    FOR_IF_KEYWORDS = [
        Terminal("IF"),
        Terminal("IN"),
        Terminal("FOR"),
        Terminal("FOR_EACH"),
        Terminal("FOR_OBJECT_ARROW"),
        Terminal("COLON"),
    ]

    # space on both sides, in ternaries and binary operators
    BINARY_OPS = [
        Terminal("QMARK"),
        Terminal("COLON"),
        Terminal("BINARY_OP"),
    ]

    def _is_equals_sign(self, terminal) -> bool:
        return (
            isinstance(self.last_rule, Token)
            and self.last_rule.value in ("attribute", "object_elem")
            and self.last_terminal == Terminal("EQ")
            and terminal != Terminal("NL_OR_COMMENT")
        )

    # pylint: disable=too-many-branches, too-many-return-statements
    def _should_add_space(self, rule, current_terminal):
        """
        This method documents the situations in which we add space around
        certain tokens while reconstructing the generated HCL.

        Additional rules can be added here if the generated HCL has
        improper whitespace (affecting parse OR affecting ability to perfectly
        reconstruct a file down to the whitespace level.)

        It has the following information available to make its decision:

          - the last token (terminal) we output
          - the last rule that token belonged to
          - the current token (terminal) we're about to output
          - the rule the current token belongs to

        This should be sufficient to make a spacing decision.
        """
        # we don't need to add multiple spaces
        if self.last_char_space:
            return False

        # we don't add a space at the start of the file
        if not self.last_terminal or not self.last_rule:
            return False

        if self._is_equals_sign(current_terminal):
            return True

        # if we're in a ternary or binary operator, add space around the operator
        if (
            isinstance(rule, Token)
            and rule.value
            in [
                "conditional",
                "binary_operator",
            ]
            and current_terminal in self.BINARY_OPS
        ):
            return True

        # if we just left a ternary or binary operator, add space around the
        # operator unless there's a newline already
        if (
            isinstance(self.last_rule, Token)
            and self.last_rule.value
            in [
                "conditional",
                "binary_operator",
            ]
            and self.last_terminal in self.BINARY_OPS
            and current_terminal != Terminal("NL_OR_COMMENT")
        ):
            return True

        # if we're in a for or if statement and find a keyword, add a space
        if (
            isinstance(rule, Token)
            and rule.value
            in [
                "for_object_expr",
                "for_cond",
                "for_intro",
            ]
            and current_terminal in self.FOR_IF_KEYWORDS
        ):
            return True

        # if we've just left a for or if statement and find a keyword, add a
        # space, unless we have a newline
        if (
            isinstance(self.last_rule, Token)
            and self.last_rule.value
            in [
                "for_object_expr",
                "for_cond",
                "for_intro",
            ]
            and self.last_terminal in self.FOR_IF_KEYWORDS
            and current_terminal != Terminal("NL_OR_COMMENT")
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

        # if we just opened a block, add a space, unless the block is empty
        # or has a newline
        if (
            isinstance(self.last_rule, Token)
            and self.last_rule.value == "block"
            and self.last_terminal == Terminal("LBRACE")
            and current_terminal not in [Terminal("RBRACE"), Terminal("NL_OR_COMMENT")]
        ):
            return True

        # if we're in a tuple or function arguments (this rule matches commas between items)
        if isinstance(self.last_rule, str) and re.match(
            r"^__(tuple|arguments)_(star|plus)_.*", self.last_rule
        ):

            # string literals, decimals, and identifiers should always be
            # preceeded by a space if they're following a comma in a tuple or
            # function arg
            if current_terminal in [
                Terminal("STRING_LIT"),
                Terminal("DECIMAL"),
                Terminal("NAME"),
            ]:
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

                # first, handle any deferred items
                if self.deferred_item is not None:
                    (
                        deferred_rule,
                        deferred_terminal,
                        deferred_value,
                    ) = self.deferred_item

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
                        self.last_rule = deferred_rule
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

                    # and do our bookkeeping so we can make an informed
                    # decision about formatting next time
                    self.last_terminal = terminal
                    self.last_rule = rule
                    if value:
                        self.last_char_space = value[-1].isspace()

            else:
                raise RuntimeError(f"Unknown bare token type: {item}")

    def reconstruct(self, tree, postproc=None, insert_spaces=False):
        """Convert a Lark.Tree AST back into a string representation of HCL."""
        return Reconstructor.reconstruct(
            self,
            tree,
            postproc,
            insert_spaces,
        )


class HCLReverseTransformer:
    """
    The reverse of hcl2.transformer.DictTransformer. This method attempts to
    convert a dict back into a working AST, which can be written back out.
    """

    @staticmethod
    def _name_to_identifier(name: str) -> Tree:
        """Converts a string to a NAME token within an identifier rule."""
        return Tree(Token("RULE", "identifier"), [Token("NAME", name)])

    @staticmethod
    def _escape_interpolated_str(interp_s: str) -> str:
        # begin by doing basic JSON string escaping, to add backslashes
        interp_s = json.dumps(interp_s)

        # find each interpolation within the string and remove the backslashes
        interp_s = reverse_quotes_within_interpolation(interp_s)
        return interp_s

    @staticmethod
    def _block_has_label(block: dict) -> bool:
        return len(block.keys()) == 1

    def __init__(self):
        pass

    def transform(self, hcl_dict: dict) -> Tree:
        """Given a dict, return a Lark.Tree representing the HCL AST."""
        level = 0
        body = self._transform_dict_to_body(hcl_dict, level)
        start = Tree(Token("RULE", "start"), [body])
        return start

    @staticmethod
    def _is_string_wrapped_tf(interp_s: str) -> bool:
        """
        Determines whether a string is a complex HCL datastructure
        wrapped in ${ interpolation } characters.
        """
        if not interp_s.startswith("${") or not interp_s.endswith("}"):
            return False

        nested_tokens = []
        for match in re.finditer(r"\$?\{|}", interp_s):
            if match.group(0) in ["${", "{"]:
                nested_tokens.append(match.group(0))
            elif match.group(0) == "}":
                nested_tokens.pop()

            # if we exit ${ interpolation } before the end of the string,
            # this interpolated string has string parts and can't represent
            # a valid HCL expression on its own (without quotes)
            if len(nested_tokens) == 0 and match.end() != len(interp_s):
                return False

        return True

    def _newline(self, level: int, count: int = 1) -> Tree:
        return Tree(
            Token("RULE", "new_line_or_comment"),
            [Token("NL_OR_COMMENT", f"\n{'  ' * level}") for _ in range(count)],
        )

    # rules: the value of a block is always an array of dicts,
    # the key is the block type
    def _list_is_a_block(self, value: list) -> bool:
        for obj in value:
            if not self._dict_is_a_block(obj):
                return False

        return True

    def _dict_is_a_block(self, sub_obj: Any) -> bool:
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

    def _calculate_block_labels(self, block: dict) -> Tuple[List[str], dict]:
        # if block doesn't have a label
        if len(block.keys()) != 1:
            return [], block

        # otherwise, find the label
        curr_label = list(block)[0]
        potential_body = block[curr_label]

        # __start_line__ and __end_line__ metadata are not labels
        if (
            "__start_line__" in potential_body.keys()
            or "__end_line__" in potential_body.keys()
        ):
            return [curr_label], potential_body

        # recurse and append the label
        next_label, block_body = self._calculate_block_labels(potential_body)
        return [curr_label] + next_label, block_body

    def _transform_dict_to_body(self, hcl_dict: dict, level: int) -> Tree:
        # we add a newline at the top of a body within a block, not the root body
        # >2 here is to ignore the __start_line__ and __end_line__ metadata
        if level > 0 and len(hcl_dict) > 2:
            children = [self._newline(level)]
        else:
            children = []

        # iterate through each attribute or sub-block of this block
        for key, value in hcl_dict.items():
            if key in ["__start_line__", "__end_line__"]:
                continue

            # construct the identifier, whether that be a block type name or an attribute key
            identifier_name = self._name_to_identifier(key)

            # first, check whether the value is a "block"
            if isinstance(value, list) and self._list_is_a_block(value):
                for block_v in value:
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
                    children.append(self._newline(level, count=2))

            # if the value isn't a block, it's an attribute
            else:
                expr_term = self._transform_value_to_expr_term(value, level)
                attribute = Tree(
                    Token("RULE", "attribute"),
                    [identifier_name, Token("EQ", " ="), expr_term],
                )
                children.append(attribute)
                children.append(self._newline(level))

        # since we're leaving a block body here, reduce the indentation of the
        # final newline if it exists
        if (
            len(children) > 0
            and isinstance(children[-1], Tree)
            and children[-1].data.type == "RULE"
            and children[-1].data.value == "new_line_or_comment"
        ):
            children[-1] = self._newline(level - 1)

        return Tree(Token("RULE", "body"), children)

    # pylint: disable=too-many-branches, too-many-return-statements
    def _transform_value_to_expr_term(self, value, level) -> Union[Token, Tree]:
        """Transforms a value from a dictionary into an "expr_term" (a value in HCL2)

        Anything passed to this function is treated "naively". Any lists passed
        are assumed to be tuples, and any dicts passed are assumed to be objects.
        No more checks will be performed for either to see if they are "blocks"
        as this check happens in `_transform_dict_to_body`.
        """

        # for lists, recursively turn the child elements into expr_terms and
        # store within a tuple
        if isinstance(value, list):
            tuple_tree = Tree(
                Token("RULE", "tuple"),
                [
                    self._transform_value_to_expr_term(tuple_v, level)
                    for tuple_v in value
                ],
            )
            return Tree(Token("RULE", "expr_term"), [tuple_tree])

        # for dicts, recursively turn the child k/v pairs into object elements
        # and store within an object
        if isinstance(value, dict):
            elems = []

            # if the object has elements, put it on a newline
            if len(value) > 0:
                elems.append(self._newline(level + 1))

            # iterate through the items and add them to the object
            for i, (k, dict_v) in enumerate(value.items()):
                if k in ["__start_line__", "__end_line__"]:
                    continue

                value_expr_term = self._transform_value_to_expr_term(dict_v, level + 1)
                elems.append(
                    Tree(
                        Token("RULE", "object_elem"),
                        [
                            Tree(
                                Token("RULE", "object_elem_key"),
                                [Tree(Token("RULE", "identifier"), [Token("NAME", k)])],
                            ),
                            Token("EQ", " ="),
                            value_expr_term,
                        ],
                    )
                )

                # add indentation appropriately
                if i < len(value) - 1:
                    elems.append(self._newline(level + 1))
                else:
                    elems.append(self._newline(level))
            return Tree(
                Token("RULE", "expr_term"), [Tree(Token("RULE", "object"), elems)]
            )

        # treat booleans appropriately
        if isinstance(value, bool):
            return Tree(
                Token("RULE", "expr_term"),
                [
                    Tree(
                        Token("RULE", "identifier"),
                        [Token("NAME", "true" if value else "false")],
                    )
                ],
            )

        # store integers as literals, digit by digit
        if isinstance(value, int):
            return Tree(
                Token("RULE", "expr_term"),
                [
                    Tree(
                        Token("RULE", "int_lit"),
                        [Token("DECIMAL", digit) for digit in str(value)],
                    )
                ],
            )

        # store strings as single literals
        if isinstance(value, str):
            # potentially unpack a complex syntax structure
            if self._is_string_wrapped_tf(value):
                # we have to unpack it by parsing it
                wrapped_value = re.match(r"\$\{(.*)}", value).group(1)  # type:ignore
                ast = reconstruction_parser().parse(f"value = {wrapped_value}")

                if ast.data != Token("RULE", "start"):
                    raise RuntimeError("Token must be `start` RULE")

                body = ast.children[0]
                if body.data != Token("RULE", "body"):
                    raise RuntimeError("Token must be `body` RULE")

                attribute = body.children[0]
                if attribute.data != Token("RULE", "attribute"):
                    raise RuntimeError("Token must be `attribute` RULE")

                if attribute.children[1] != Token("EQ", " ="):
                    raise RuntimeError("Token must be `EQ (=)` rule")

                parsed_value = attribute.children[2]

                if parsed_value.data == Token("RULE", "expr_term"):
                    return parsed_value

                # wrap other types of syntax as an expression (in parentheses)
                return Tree(Token("RULE", "expr_term"), [parsed_value])

            # otherwise it's just a string.
            return Tree(
                Token("RULE", "expr_term"),
                [Token("STRING_LIT", self._escape_interpolated_str(value))],
            )

        # otherwise, we don't know the type
        raise RuntimeError(f"Unknown type to transform {type(value)}")


hcl2_reconstructor = HCLReconstructor(reconstruction_parser())
hcl2_reverse_transformer = HCLReverseTransformer()
