from typing import List, Optional, Tuple, Any, Union

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expressions import ExprTermRule, ExpressionRule
from hcl2.rule_transformer.rules.literal_rules import IdentifierRule
from hcl2.rule_transformer.rules.tokens import (
    DOT,
    IntLiteral,
    LSQB,
    RSQB,
    ATTR_SPLAT,
)
from hcl2.rule_transformer.rules.whitespace import (
    InlineCommentMixIn,
    NewLineOrCommentRule,
)
from hcl2.rule_transformer.utils import (
    SerializationOptions,
    to_dollar_string,
    SerializationContext,
)


class ShortIndexRule(LarkRule):

    _children: Tuple[
        DOT,
        IntLiteral,
    ]

    @staticmethod
    def lark_name() -> str:
        return "short_index"

    @property
    def index(self):
        return self.children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return f".{self.index.serialize(options)}"


class SqbIndexRule(InlineCommentMixIn):
    _children: Tuple[
        LSQB,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
        Optional[NewLineOrCommentRule],
        RSQB,
    ]

    @staticmethod
    def lark_name() -> str:
        return "braces_index"

    @property
    def index_expression(self):
        return self.children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return f"[{self.index_expression.serialize(options)}]"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._insert_optionals(children, [1, 3])
        super().__init__(children, meta)


class IndexExprTermRule(ExpressionRule):

    _children: Tuple[ExprTermRule, SqbIndexRule]

    @staticmethod
    def lark_name() -> str:
        return "index_expr_term"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        with context.modify(inside_dollar_string=True):
            result = f"{self.children[0].serialize(options)}{self.children[1].serialize(options)}"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class GetAttrRule(LarkRule):

    _children: Tuple[
        DOT,
        IdentifierRule,
    ]

    @staticmethod
    def lark_name() -> str:
        return "get_attr"

    @property
    def identifier(self) -> IdentifierRule:
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return f".{self.identifier.serialize(options, context)}"


class GetAttrExprTermRule(ExpressionRule):

    _children: Tuple[
        ExprTermRule,
        GetAttrRule,
    ]

    @staticmethod
    def lark_name() -> str:
        return "get_attr_expr_term"

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[0]

    @property
    def get_attr(self) -> GetAttrRule:
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        with context.modify(inside_dollar_string=True):
            result = f"{self.expr_term.serialize(options, context)}{self.get_attr.serialize(options, context)}"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class AttrSplatRule(LarkRule):
    _children: Tuple[
        ATTR_SPLAT,
        Tuple[Union[GetAttrRule, Union[SqbIndexRule, ShortIndexRule]], ...],
    ]

    @staticmethod
    def lark_name() -> str:
        return "attr_splat"

    @property
    def get_attrs(
        self,
    ) -> List[Union[GetAttrRule, Union[SqbIndexRule, ShortIndexRule]]]:
        return self._children[1:]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return ".*" + "".join(
            get_attr.serialize(options, context) for get_attr in self.get_attrs
        )


class AttrSplatExprTermRule(ExpressionRule):

    _children: Tuple[ExprTermRule, AttrSplatRule]

    @staticmethod
    def lark_name() -> str:
        return "attr_splat_expr_term"

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[0]

    @property
    def attr_splat(self) -> AttrSplatRule:
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        with context.modify(inside_dollar_string=True):
            result = f"{self.expr_term.serialize(options, context)}{self.attr_splat.serialize(options, context)}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class FullSplatRule(LarkRule):
    _children: Tuple[
        ATTR_SPLAT,
        Tuple[Union[GetAttrRule, Union[SqbIndexRule, ShortIndexRule]], ...],
    ]

    @staticmethod
    def lark_name() -> str:
        return "full_splat"

    @property
    def get_attrs(
        self,
    ) -> List[Union[GetAttrRule, Union[SqbIndexRule, ShortIndexRule]]]:
        return self._children[1:]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return "[*]" + "".join(
            get_attr.serialize(options, context) for get_attr in self.get_attrs
        )


class FullSplatExprTermRule(ExpressionRule):
    _children: Tuple[ExprTermRule, FullSplatRule]

    @staticmethod
    def lark_name() -> str:
        return "full_splat_expr_term"

    @property
    def expr_term(self) -> ExprTermRule:
        return self._children[0]

    @property
    def attr_splat(self) -> FullSplatRule:
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        with context.modify(inside_dollar_string=True):
            result = f"{self.expr_term.serialize(options, context)}{self.attr_splat.serialize(options, context)}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result
