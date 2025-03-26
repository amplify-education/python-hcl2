from abc import ABC
from typing import Any, Tuple, Optional, List

from lark import Tree, Token
from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import (
    LarkRule,
    LarkToken,
    LPAR_TOKEN,
    RPAR_TOKEN,
)
from hcl2.rule_transformer.rules.whitespace import NewLineOrCommentRule
from hcl2.rule_transformer.rules.token_sequence import BinaryOperatorRule
from hcl2.rule_transformer.utils import (
    wrap_into_parentheses,
    to_dollar_string,
    unwrap_dollar_string,
)


class Expression(LarkRule, ABC):
    @staticmethod
    def rule_name() -> str:
        return "expression"


class ExprTermRule(Expression):

    _children: Tuple[
        Optional[LPAR_TOKEN],
        Optional[NewLineOrCommentRule],
        Expression,
        Optional[NewLineOrCommentRule],
        Optional[RPAR_TOKEN],
    ]

    @staticmethod
    def rule_name() -> str:
        return "expr_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._parentheses = False
        if (
            isinstance(children[0], LarkToken)
            and children[0].name == "LPAR"
            and isinstance(children[-1], LarkToken)
            and children[-1].name == "RPAR"
        ):
            self._parentheses = True
            children = children[1:-1]
        super().__init__(children, meta)

    @property
    def parentheses(self) -> bool:
        return self._parentheses

    def serialize(self) -> Any:
        result = self._children[0].serialize()
        if self.parentheses:
            result = wrap_into_parentheses(result)
            result = to_dollar_string(result)
        return result

    def tree(self) -> Tree:
        tree = super().tree()
        if self.parentheses:
            return Tree(
                tree.data, [Token("LPAR", "("), *tree.children, Token("RPAR", ")")]
            )
        return tree


class ConditionalRule(LarkRule):

    _children: Tuple[
        Expression,
        Expression,
        Expression,
    ]

    @staticmethod
    def rule_name():
        return "conditional"

    @property
    def condition(self) -> Expression:
        return self._children[0]

    @property
    def if_true(self) -> Expression:
        return self._children[1]

    @property
    def if_false(self) -> Expression:
        return self._children[2]

    def __init__(self, children, meta: Optional[Meta] = None):
        super().__init__(children, meta)

    def serialize(self) -> Any:
        result = f"{self.condition.serialize()} ? {self.if_true.serialize()} : {self.if_false.serialize()}"
        return to_dollar_string(result)


class BinaryTermRule(LarkRule):

    _children: Tuple[
        BinaryOperatorRule,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
    ]

    @staticmethod
    def rule_name() -> str:
        return "binary_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        if len(children) == 2:
            children.insert(1, None)
        super().__init__(children, meta)

    @property
    def binary_operator(self) -> BinaryOperatorRule:
        return self._children[0]

    @property
    def comment(self) -> Optional[NewLineOrCommentRule]:
        return self._children[1]

    @property
    def has_comment(self) -> bool:
        return self.comment is not None

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[2]

    def serialize(self) -> Any:
        return f"{self.binary_operator.serialize()} {self.expr_term.serialize()}"


class BinaryOpRule(Expression):
    _children: Tuple[
        ExprTermRule,
        BinaryTermRule,
        NewLineOrCommentRule,
    ]

    @staticmethod
    def rule_name() -> str:
        return "binary_op"

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[0]

    @property
    def binary_term(self) -> BinaryTermRule:
        return self._children[1]

    def serialize(self) -> Any:
        lhs = self.expr_term.serialize()
        operator = self.binary_term.binary_operator.serialize()
        rhs = self.binary_term.expr_term.serialize()
        rhs = unwrap_dollar_string(rhs)
        return to_dollar_string(f"{lhs} {operator} {rhs}")


class UnaryOpRule(Expression):

    _children: Tuple[LarkToken, ExprTermRule]

    @staticmethod
    def rule_name() -> str:
        return "unary_op"

    @property
    def operator(self) -> str:
        return str(self._children[0])

    @property
    def expr_term(self):
        return self._children[1]

    def serialize(self) -> Any:
        return to_dollar_string(f"{self.operator}{self.expr_term.serialize()}")
