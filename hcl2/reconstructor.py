"""Reconstruct HCL2 text from a Lark Tree AST."""
from typing import List, Optional, Union

from lark import Tree, Token
from hcl2.rules import tokens
from hcl2.rules.base import BlockRule
from hcl2.rules.containers import ObjectElemRule
from hcl2.rules.for_expressions import ForIntroRule, ForTupleExprRule, ForObjectExprRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.strings import StringRule
from hcl2.rules.expressions import (
    ExprTermRule,
    ConditionalRule,
    UnaryOpRule,
)


class HCLReconstructor:
    """This class converts a Lark.Tree AST back into a string representing the underlying HCL code."""

    _binary_op_types = {
        "DOUBLE_EQ",
        "NEQ",
        "LT",
        "GT",
        "LEQ",
        "GEQ",
        "MINUS",
        "ASTERISK",
        "SLASH",
        "PERCENT",
        "DOUBLE_AMP",
        "DOUBLE_PIPE",
        "PLUS",
    }

    def __init__(self):
        self._last_was_space = True
        self._current_indent = 0
        self._last_token_name: Optional[str] = None
        self._last_rule_name: Optional[str] = None

    def _reset_state(self):
        """Reset state tracking for formatting decisions."""
        self._last_was_space = True
        self._current_indent = 0
        self._last_token_name = None
        self._last_rule_name = None

    # pylint:disable=R0911,R0912
    def _should_add_space_before(
        self, current_node: Union[Tree, Token], parent_rule_name: Optional[str] = None
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
            if parent_rule_name == ConditionalRule.lark_name() and (
                token_type in [tokens.COLON.lark_name(), tokens.QMARK.lark_name()]
                or self._last_token_name
                in [tokens.COLON.lark_name(), tokens.QMARK.lark_name()]
            ):
                # COLON may already carry leading whitespace from the grammar
                if token_type == tokens.COLON.lark_name() and str(
                    current_node
                ).startswith((" ", "\t")):
                    return False
                return True

            # Space before colon in for_intro
            if (
                parent_rule_name == ForIntroRule.lark_name()
                and token_type == tokens.COLON.lark_name()
            ):
                if str(current_node).startswith((" ", "\t")):
                    return False
                return True

            # Space after commas in tuples and function arguments...
            if self._last_token_name == tokens.COMMA.lark_name():
                # ... except before closing brackets or newlines
                if token_type in (tokens.RSQB.lark_name(), "NL_OR_COMMENT"):
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
            # ... except before newlines which provide their own whitespace
            if self._last_token_name == tokens.ELLIPSIS.lark_name():
                if token_type == "NL_OR_COMMENT":
                    return False
                return True

            # Space around EQ and COLON separators in attributes/object elements.
            # Both terminals may carry leading whitespace from the original
            # source (e.g. "   =" for aligned attributes, " :" for object
            # elements).  Skip the automatic space when the token already
            # provides it.  COLON only gets space if it already has leading
            # whitespace (unlike EQ which always gets at least one space).
            if token_type == tokens.EQ.lark_name():
                if str(current_node).startswith((" ", "\t")):
                    return False
                return True
            if token_type == tokens.COLON.lark_name():
                return False
            if self._last_token_name == tokens.EQ.lark_name():
                # Don't add space before newlines which provide their own whitespace
                if token_type == "NL_OR_COMMENT":
                    return False
                return True

            # Don't add space around operator tokens inside unary_op
            if parent_rule_name == UnaryOpRule.lark_name():
                return False

            if (
                token_type in self._binary_op_types
                or self._last_token_name in self._binary_op_types
            ):
                return True

        elif isinstance(current_node, Tree):
            rule_name = current_node.data

            # Space after binary operator tokens before a tree node (e.g. && !foo)
            if self._last_token_name in self._binary_op_types:
                return True

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

            # Space after QMARK/COLON in conditional expressions
            if (
                parent_rule_name == ConditionalRule.lark_name()
                and self._last_token_name
                in [tokens.COLON.lark_name(), tokens.QMARK.lark_name()]
            ):
                return True

            # Space after colon in for expressions and object elements
            # (before value expression, but not before newline/comment
            # which provides its own whitespace)
            if (
                self._last_token_name == tokens.COLON.lark_name()
                and parent_rule_name
                in [
                    ForTupleExprRule.lark_name(),
                    ForObjectExprRule.lark_name(),
                    ObjectElemRule.lark_name(),
                ]
                and rule_name != "new_line_or_comment"
            ):
                return True

        return False

    def _reconstruct_tree(
        self, tree: Tree, parent_rule_name: Optional[str] = None
    ) -> List[str]:
        """Recursively reconstruct a Tree node into HCL text fragments."""
        result = []
        rule_name = tree.data

        # Check spacing BEFORE processing children, while _last_rule_name
        # still reflects the previous sibling (not a child of this tree).
        needs_space = self._should_add_space_before(tree, parent_rule_name)
        if needs_space:
            # A space will be inserted before this tree's output, so tell
            # children that the last character was a space to prevent the
            # first child from adding a duplicate leading space.
            self._last_was_space = True

        if rule_name == UnaryOpRule.lark_name():
            for i, child in enumerate(tree.children):
                result.extend(self._reconstruct_node(child, rule_name))
                if i == 0:
                    # Suppress space between unary operator and its operand
                    self._last_was_space = True

        elif rule_name == ExprTermRule.lark_name():
            for child in tree.children:
                result.extend(self._reconstruct_node(child, rule_name))

        else:
            for child in tree.children:
                result.extend(self._reconstruct_node(child, rule_name))

        if needs_space:
            result.insert(0, " ")

        # Update state tracking
        self._last_rule_name = rule_name
        if result:
            self._last_was_space = result[-1].endswith(" ") or result[-1].endswith("\n")

        return result

    def _reconstruct_token(
        self, token: Token, parent_rule_name: Optional[str] = None
    ) -> str:
        """Reconstruct a Token node into HCL text fragments."""
        result = str(token.value)
        if self._should_add_space_before(token, parent_rule_name):
            result = " " + result

        self._last_token_name = token.type
        if len(token) != 0:
            self._last_was_space = result[-1].endswith(" ") or result[-1].endswith("\n")

        return result

    def _reconstruct_node(
        self, node: Union[Tree, Token], parent_rule_name: Optional[str] = None
    ) -> List[str]:
        """Reconstruct any node (Tree or Token) into HCL text fragments."""
        if isinstance(node, Tree):
            return self._reconstruct_tree(node, parent_rule_name)
        if isinstance(node, Token):
            return [self._reconstruct_token(node, parent_rule_name)]
        # Fallback: convert to string
        return [str(node)]

    def reconstruct(self, tree: Tree, postproc=None) -> str:
        """Convert a Lark.Tree AST back into a string representation of HCL."""
        # Reset state
        self._reset_state()

        # Reconstruct the tree
        fragments = self._reconstruct_node(tree)

        # Join fragments and apply post-processing
        result = "".join(fragments)

        if postproc:
            result = postproc(result)

        # The grammar's body rule ends with an optional new_line_or_comment
        # which captures the final newline.  The parser often produces two
        # NL_OR_COMMENT tokens for a single trailing newline (the statement
        # separator plus the EOF newline), resulting in a spurious blank line.
        # Strip exactly one trailing newline when there are two or more.
        if result.endswith("\n\n"):
            result = result[:-1]

        # Ensure file ends with newline
        if result and not result.endswith("\n"):
            result += "\n"

        return result
