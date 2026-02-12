from typing import List, Union

from lark import Tree, Token
from hcl2.rule_transformer.rules import tokens
from hcl2.rule_transformer.rules.base import BlockRule
from hcl2.rule_transformer.rules.for_expressions import ForIntroRule
from hcl2.rule_transformer.rules.literal_rules import IdentifierRule
from hcl2.rule_transformer.rules.strings import StringRule
from hcl2.rule_transformer.rules.expressions import ExprTermRule, ConditionalRule


class HCLReconstructor:
    """This class converts a Lark.Tree AST back into a string representing the underlying HCL code."""

    def __init__(self):
        self._reset_state()

    def _reset_state(self):
        """State tracking for formatting decisions"""
        self._last_was_space = True
        self._current_indent = 0
        self._last_token_name = None
        self._last_rule_name = None
        self._in_parentheses = False
        self._in_object = False
        self._in_tuple = False

    def _should_add_space_before(
        self, current_node: Union[Tree, Token], parent_rule_name: str = None
    ) -> bool:
        """Determine if we should add a space before the current token/rule."""

        # Don't add space if we already have one
        if self._last_was_space:
            return False

        # Don't add space at the beginning
        if self._last_token_name is None:
            return False

        if isinstance(current_node, Token):
            token_type = current_node.type

            # Space before '{' in blocks
            if (
                token_type == tokens.LBRACE.lark_name()
                and parent_rule_name == BlockRule.lark_name()
            ):
                return True

            # Space around Conditional Expression operators
            if (
                parent_rule_name == ConditionalRule.lark_name()
                and token_type in [tokens.COLON.lark_name(), tokens.QMARK.lark_name()]
                or self._last_token_name
                in [tokens.COLON.lark_name(), tokens.QMARK.lark_name()]
            ):
                return True

            # Space after
            if (
                parent_rule_name == ForIntroRule.lark_name()
                and token_type == tokens.COLON.lark_name()
            ):

                return True

            # Space after commas in tuples and function arguments...
            if self._last_token_name == tokens.COMMA.lark_name():
                # ... except for last comma
                if token_type == tokens.RSQB.lark_name():
                    return False
                return True

            if token_type in [
                tokens.FOR.lark_name(),
                tokens.IN.lark_name(),
                tokens.IF.lark_name(),
                tokens.ELLIPSIS.lark_name(),
            ]:
                return True

            if (
                self._last_token_name
                in [
                    tokens.FOR.lark_name(),
                    tokens.IN.lark_name(),
                    tokens.IF.lark_name(),
                ]
                and token_type != "NL_OR_COMMENT"
            ):
                return True

            # Space around for_object arrow
            if tokens.FOR_OBJECT_ARROW.lark_name() in [
                token_type,
                self._last_token_name,
            ]:
                return True

            # Space after ellipsis in function arguments
            if self._last_token_name == tokens.ELLIPSIS.lark_name():
                return True

            if tokens.EQ.lark_name() in [token_type, self._last_token_name]:
                return True

            # space around binary operators
            if tokens.BINARY_OP.lark_name() in [token_type, self._last_token_name]:
                return True

        elif isinstance(current_node, Tree):
            rule_name = current_node.data

            if parent_rule_name == BlockRule.lark_name():
                # Add space between multiple string/identifier labels in blocks
                if rule_name in [
                    StringRule.lark_name(),
                    IdentifierRule.lark_name(),
                ] and self._last_rule_name in [
                    StringRule.lark_name(),
                    IdentifierRule.lark_name(),
                ]:
                    return True

        return False

    def _reconstruct_tree(self, tree: Tree, parent_rule_name: str = None) -> List[str]:
        """Recursively reconstruct a Tree node into HCL text fragments."""
        result = []
        rule_name = tree.data

        if rule_name == ExprTermRule.lark_name():
            # Check if parenthesized
            if (
                len(tree.children) >= 3
                and isinstance(tree.children[0], Token)
                and tree.children[0].type == tokens.LPAR.lark_name()
                and isinstance(tree.children[-1], Token)
                and tree.children[-1].type == tokens.RPAR.lark_name()
            ):
                self._in_parentheses = True

            for child in tree.children:
                result.extend(self._reconstruct_node(child, rule_name))

            self._in_parentheses = False

        else:
            for child in tree.children:
                result.extend(self._reconstruct_node(child, rule_name))

        if self._should_add_space_before(tree, parent_rule_name):
            result.insert(0, " ")

        # Update state tracking
        self._last_rule_name = rule_name
        if result:
            self._last_was_space = result[-1].endswith(" ") or result[-1].endswith("\n")

        return result

    def _reconstruct_token(self, token: Token, parent_rule_name: str = None) -> str:
        """Reconstruct a Token node into HCL text fragments."""
        result = str(token.value)
        if self._should_add_space_before(token, parent_rule_name):
            result = " " + result

        self._last_token_name = token.type
        if len(token) != 0:
            self._last_was_space = result[-1].endswith(" ") or result[-1].endswith("\n")

        return result

    def _reconstruct_node(
        self, node: Union[Tree, Token], parent_rule_name: str = None
    ) -> List[str]:
        """Reconstruct any node (Tree or Token) into HCL text fragments."""
        if isinstance(node, Tree):
            return self._reconstruct_tree(node, parent_rule_name)
        elif isinstance(node, Token):
            return [self._reconstruct_token(node, parent_rule_name)]
        else:
            # Fallback: convert to string
            return [str(node)]

    def reconstruct(self, tree: Tree, postproc=None, insert_spaces=False) -> str:
        """Convert a Lark.Tree AST back into a string representation of HCL."""
        # Reset state
        self._reset_state()

        # Reconstruct the tree
        fragments = self._reconstruct_node(tree)

        # Join fragments and apply post-processing
        result = "".join(fragments)

        if postproc:
            result = postproc(result)

        # Ensure file ends with newline
        if result and not result.endswith("\n"):
            result += "\n"

        return result
