"""Rule classes for HCL2 indexing, attribute access, and splat expressions."""

from typing import List, Optional, Tuple, Any, Union

from lark.tree import Meta

from hcl2.rules.abstract import LarkRule
from hcl2.rules.expressions import ExprTermRule, ExpressionRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import (
    DOT,
    IntLiteral,
    LSQB,
    RSQB,
    ATTR_SPLAT,
)
from hcl2.rules.whitespace import (
    InlineCommentMixIn,
    NewLineOrCommentRule,
)
from hcl2.utils import (
    SerializationOptions,
    to_dollar_string,
    SerializationContext,
)


class ShortIndexRule(LarkRule):
    """Rule for dot-numeric index access (e.g. .0)."""

    _children_layout: Tuple[
        DOT,
        IntLiteral,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "short_index"

    @property
    def index(self):
        """Return the index token."""
        return self.children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to '.N' string."""
        return f".{self.index.serialize(options)}"


class SqbIndexRule(InlineCommentMixIn):
    """Rule for square-bracket index access (e.g. [expr])."""

    _children_layout: Tuple[
        LSQB,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
        Optional[NewLineOrCommentRule],
        RSQB,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "braces_index"

    @property
    def index_expression(self):
        """Return the index expression inside the brackets."""
        return self.children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to '[expr]' string."""
        return f"[{self.index_expression.serialize(options)}]"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._insert_optionals(children, [1, 3])
        super().__init__(children, meta)


class IndexExprTermRule(ExpressionRule):
    """Rule for index access on an expression term."""

    _children_layout: Tuple[ExprTermRule, SqbIndexRule]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "index_expr_term"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'expr[index]' string."""
        with context.modify(inside_dollar_string=True):
            expr = self.children[0].serialize(options)
            index = self.children[1].serialize(options)
            result = f"{expr}{index}"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class GetAttrRule(LarkRule):
    """Rule for dot-attribute access (e.g. .name)."""

    _children_layout: Tuple[
        DOT,
        IdentifierRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "get_attr"

    @property
    def identifier(self) -> IdentifierRule:
        """Return the accessed identifier."""
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to '.identifier' string."""
        return f".{self.identifier.serialize(options, context)}"


class GetAttrExprTermRule(ExpressionRule):
    """Rule for attribute access on an expression term."""

    _children_layout: Tuple[
        ExprTermRule,
        GetAttrRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "get_attr_expr_term"

    @property
    def expr_term(self) -> ExprTermRule:
        """Return the base expression term."""
        return self._children[0]

    @property
    def get_attr(self) -> GetAttrRule:
        """Return the attribute access rule."""
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'expr.attr' string."""
        with context.modify(inside_dollar_string=True):
            expr = self.expr_term.serialize(options, context)
            attr = self.get_attr.serialize(options, context)
            result = f"{expr}{attr}"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class AttrSplatRule(LarkRule):
    """Rule for attribute splat expressions (e.g. .*.attr)."""

    _children_layout: Tuple[
        ATTR_SPLAT,
        Tuple[Union[GetAttrRule, Union[SqbIndexRule, ShortIndexRule]], ...],
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "attr_splat"

    @property
    def get_attrs(
        self,
    ) -> List[Union[GetAttrRule, SqbIndexRule, ShortIndexRule]]:
        """Return the trailing accessor chain."""
        return self._children[1:]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to '.*...' string."""
        return ".*" + "".join(
            get_attr.serialize(options, context) for get_attr in self.get_attrs
        )


class AttrSplatExprTermRule(ExpressionRule):
    """Rule for attribute splat on an expression term."""

    _children_layout: Tuple[ExprTermRule, AttrSplatRule]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "attr_splat_expr_term"

    @property
    def expr_term(self) -> ExprTermRule:
        """Return the base expression term."""
        return self._children[0]

    @property
    def attr_splat(self) -> AttrSplatRule:
        """Return the attribute splat rule."""
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'expr.*...' string."""
        with context.modify(inside_dollar_string=True):
            expr = self.expr_term.serialize(options, context)
            splat = self.attr_splat.serialize(options, context)
            result = f"{expr}{splat}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class FullSplatRule(LarkRule):
    """Rule for full splat expressions (e.g. [*].attr)."""

    _children_layout: Tuple[
        ATTR_SPLAT,
        Tuple[Union[GetAttrRule, Union[SqbIndexRule, ShortIndexRule]], ...],
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "full_splat"

    @property
    def get_attrs(
        self,
    ) -> List[Union[GetAttrRule, SqbIndexRule, ShortIndexRule]]:
        """Return the trailing accessor chain."""
        return self._children[1:]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to '[*]...' string."""
        return "[*]" + "".join(
            get_attr.serialize(options, context) for get_attr in self.get_attrs
        )


class FullSplatExprTermRule(ExpressionRule):
    """Rule for full splat on an expression term."""

    _children_layout: Tuple[ExprTermRule, FullSplatRule]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "full_splat_expr_term"

    @property
    def expr_term(self) -> ExprTermRule:
        """Return the base expression term."""
        return self._children[0]

    @property
    def attr_splat(self) -> FullSplatRule:
        """Return the full splat rule."""
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'expr[*]...' string."""
        with context.modify(inside_dollar_string=True):
            expr = self.expr_term.serialize(options, context)
            splat = self.attr_splat.serialize(options, context)
            result = f"{expr}{splat}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result
