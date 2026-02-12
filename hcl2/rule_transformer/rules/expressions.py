from abc import ABC
from copy import deepcopy
from typing import Any, Tuple, Optional

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import (
    LarkToken,
)
from hcl2.rule_transformer.rules.literal_rules import BinaryOperatorRule
from hcl2.rule_transformer.rules.tokens import LPAR, RPAR, QMARK, COLON
from hcl2.rule_transformer.rules.whitespace import (
    NewLineOrCommentRule,
    InlineCommentMixIn,
)
from hcl2.rule_transformer.utils import (
    wrap_into_parentheses,
    to_dollar_string,
    SerializationOptions,
    SerializationContext,
)


class ExpressionRule(InlineCommentMixIn, ABC):
    @staticmethod
    def lark_name() -> str:
        return "expression"

    def __init__(self, children, meta: Optional[Meta] = None):
        super().__init__(children, meta)


class ExprTermRule(ExpressionRule):

    type_ = Tuple[
        Optional[LPAR],
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        Optional[RPAR],
    ]

    _children: type_

    @staticmethod
    def lark_name() -> str:
        return "expr_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._parentheses = False
        if (
            isinstance(children[0], LarkToken)
            and children[0].lark_name() == "LPAR"
            and isinstance(children[-1], LarkToken)
            and children[-1].lark_name() == "RPAR"
        ):
            self._parentheses = True
        else:
            children = [None, *children, None]
        self._insert_optionals(children, [1, 3])
        super().__init__(children, meta)

    @property
    def parentheses(self) -> bool:
        return self._parentheses

    @property
    def expression(self) -> ExpressionRule:
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        result = self.expression.serialize(options, context)

        if self.parentheses:
            result = wrap_into_parentheses(result)
            if not context.inside_dollar_string:
                result = to_dollar_string(result)

        return result


class ConditionalRule(ExpressionRule):

    _children: Tuple[
        ExpressionRule,
        QMARK,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        COLON,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
    ]

    @staticmethod
    def lark_name() -> str:
        return "conditional"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._insert_optionals(children, [2, 4, 6])
        super().__init__(children, meta)

    @property
    def condition(self) -> ExpressionRule:
        return self._children[0]

    @property
    def if_true(self) -> ExpressionRule:
        return self._children[3]

    @property
    def if_false(self) -> ExpressionRule:
        return self._children[7]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        with context.modify(inside_dollar_string=True):
            result = (
                f"{self.condition.serialize(options, context)} "
                f"? {self.if_true.serialize(options, context)} "
                f": {self.if_false.serialize(options, context)}"
            )

        if not context.inside_dollar_string:
            result = to_dollar_string(result)

        return result


class BinaryTermRule(ExpressionRule):

    _children: Tuple[
        BinaryOperatorRule,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
    ]

    @staticmethod
    def lark_name() -> str:
        return "binary_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._insert_optionals(children, [1])
        super().__init__(children, meta)

    @property
    def binary_operator(self) -> BinaryOperatorRule:
        return self._children[0]

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return f"{self.binary_operator.serialize(options, context)} {self.expr_term.serialize(options, context)}"


class BinaryOpRule(ExpressionRule):
    _children: Tuple[
        ExprTermRule,
        BinaryTermRule,
        Optional[NewLineOrCommentRule],
    ]

    @staticmethod
    def lark_name() -> str:
        return "binary_op"

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[0]

    @property
    def binary_term(self) -> BinaryTermRule:
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:

        with context.modify(inside_dollar_string=True):
            lhs = self.expr_term.serialize(options, context)
            operator = self.binary_term.binary_operator.serialize(options, context)
            rhs = self.binary_term.expr_term.serialize(options, context)

        result = f"{lhs} {operator} {rhs}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class UnaryOpRule(ExpressionRule):

    _children: Tuple[LarkToken, ExprTermRule]

    @staticmethod
    def lark_name() -> str:
        return "unary_op"

    @property
    def operator(self) -> str:
        return str(self._children[0])

    @property
    def expr_term(self):
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return to_dollar_string(
            f"{self.operator}{self.expr_term.serialize(options, context)}"
        )
