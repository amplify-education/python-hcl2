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
    SerializationOptions,
)


class Expression(LarkRule, ABC):
    @staticmethod
    def rule_name() -> str:
        return "expression"

    def __init__(self, children, meta: Optional[Meta] = None):
        super().__init__(children, meta)

    def inline_comments(self):
        result = []
        for child in self._children:

            if isinstance(child, NewLineOrCommentRule):
                result.extend(child.to_list())

            elif isinstance(child, Expression):
                result.extend(child.inline_comments())

        return result

    def _possibly_insert_null_comments(self, children: List, indexes: List[int] = None):
        for index in indexes:
            try:
                child = children[index]
            except IndexError:
                children.insert(index, None)
            else:
                if not isinstance(child, NewLineOrCommentRule):
                    children.insert(index, None)


class ExprTermRule(Expression):

    type_ = Tuple[
        Optional[LPAR_TOKEN],
        Optional[NewLineOrCommentRule],
        Expression,
        Optional[NewLineOrCommentRule],
        Optional[RPAR_TOKEN],
    ]

    _children: type_

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
        else:
            children = [None, *children, None]

        self._possibly_insert_null_comments(children, [1, 3])
        super().__init__(children, meta)

    @property
    def parentheses(self) -> bool:
        return self._parentheses

    @property
    def expression(self) -> Expression:
        return self._children[2]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        result = self.expression.serialize(options)
        if self.parentheses:
            result = wrap_into_parentheses(result)
            result = to_dollar_string(result)
        return result


class ConditionalRule(Expression):

    _children: Tuple[
        Expression,
        Optional[NewLineOrCommentRule],
        Expression,
        Optional[NewLineOrCommentRule],
        Optional[NewLineOrCommentRule],
        Expression,
    ]

    @staticmethod
    def rule_name():
        return "conditional"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._possibly_insert_null_comments(children, [1, 3, 4])
        super().__init__(children, meta)

    @property
    def condition(self) -> Expression:
        return self._children[0]

    @property
    def if_true(self) -> Expression:
        return self._children[2]

    @property
    def if_false(self) -> Expression:
        return self._children[5]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        result = f"{self.condition.serialize(options)} ? {self.if_true.serialize(options)} : {self.if_false.serialize(options)}"
        return to_dollar_string(result)


class BinaryTermRule(Expression):

    _children: Tuple[
        BinaryOperatorRule,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
    ]

    @staticmethod
    def rule_name() -> str:
        return "binary_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._possibly_insert_null_comments(children, [1])
        super().__init__(children, meta)

    @property
    def binary_operator(self) -> BinaryOperatorRule:
        return self._children[0]

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[2]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return f"{self.binary_operator.serialize(options)} {self.expr_term.serialize(options)}"


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

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        lhs = self.expr_term.serialize(options)
        operator = self.binary_term.binary_operator.serialize(options)
        rhs = self.binary_term.expr_term.serialize(options)
        # below line is to avoid dollar string nested inside another dollar string, e.g.:
        #   hcl2: 15 + (10 * 12)
        #   desired json: "${15 + (10 * 12)}"
        #   undesired json: "${15 + ${(10 * 12)}}"
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

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return to_dollar_string(f"{self.operator}{self.expr_term.serialize(options)}")
