from abc import ABC
from copy import deepcopy
from typing import Any, Tuple, Optional

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import (
    LarkToken,
)
from hcl2.rule_transformer.rules.literal_rules import BinaryOperatorRule
from hcl2.rule_transformer.rules.tokens import LPAR_TOKEN, RPAR_TOKEN, QMARK_TOKEN, COLON_TOKEN
from hcl2.rule_transformer.rules.whitespace import (
    NewLineOrCommentRule,
    InlineCommentMixIn,
)
from hcl2.rule_transformer.utils import (
    wrap_into_parentheses,
    to_dollar_string,
    unwrap_dollar_string,
    SerializationOptions,
)


class Expression(InlineCommentMixIn, ABC):
    @property
    def lark_name(self) -> str:
        return "expression"

    def __init__(self, children, meta: Optional[Meta] = None):
        super().__init__(children, meta)


class ExprTermRule(Expression):

    type_ = Tuple[
        Optional[LPAR_TOKEN],
        Optional[NewLineOrCommentRule],
        Expression,
        Optional[NewLineOrCommentRule],
        Optional[RPAR_TOKEN],
    ]

    _children: type_

    @property
    def lark_name(self) -> str:
        return "expr_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._parentheses = False
        if (
            isinstance(children[0], LarkToken)
            and children[0].lark_name == "LPAR"
            and isinstance(children[-1], LarkToken)
            and children[-1].lark_name == "RPAR"
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

    def serialize(self , unwrap: bool = False, options: SerializationOptions = SerializationOptions()) -> Any:
        result = self.expression.serialize(options)
        if self.parentheses:
            result = wrap_into_parentheses(result)
            result = to_dollar_string(result)
            
        if options.unwrap_dollar_string:
            result = unwrap_dollar_string(result)
        return result


class ConditionalRule(Expression):

    _children: Tuple[
        Expression,
        QMARK_TOKEN,
        Optional[NewLineOrCommentRule],
        Expression,
        Optional[NewLineOrCommentRule],
        COLON_TOKEN,
        Optional[NewLineOrCommentRule],
        Expression,
    ]

    @property
    def lark_name(self) -> str:
        return "conditional"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._possibly_insert_null_comments(children, [2, 4, 6])
        super().__init__(children, meta)

    @property
    def condition(self) -> Expression:
        return self._children[0]

    @property
    def if_true(self) -> Expression:
        return self._children[3]

    @property
    def if_false(self) -> Expression:
        return self._children[7]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        options = options.replace(unwrap_dollar_string=True)
        print(self.condition)
        result = f"{self.condition.serialize(options)} ? {self.if_true.serialize(options)} : {self.if_false.serialize(options)}"
        return to_dollar_string(result)


class BinaryTermRule(Expression):

    _children: Tuple[
        BinaryOperatorRule,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
    ]

    @property
    def lark_name(self) -> str:
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
        Optional[NewLineOrCommentRule],
    ]

    @property
    def lark_name(self) -> str:
        return "binary_op"

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[0]

    @property
    def binary_term(self) -> BinaryTermRule:
        return self._children[1]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        children_options = options.replace(unwrap_dollar_string=True)
        lhs = self.expr_term.serialize(children_options)
        operator = self.binary_term.binary_operator.serialize(children_options)
        rhs = self.binary_term.expr_term.serialize(children_options)

        result = f"{lhs} {operator} {rhs}"
        if options.unwrap_dollar_string:
            return result
        return to_dollar_string(result)


class UnaryOpRule(Expression):

    _children: Tuple[LarkToken, ExprTermRule]

    @property
    def lark_name(self) -> str:
        return "unary_op"

    @property
    def operator(self) -> str:
        return str(self._children[0])

    @property
    def expr_term(self):
        return self._children[1]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return to_dollar_string(f"{self.operator}{self.expr_term.serialize(options)}")
