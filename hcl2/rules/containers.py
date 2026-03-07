"""Rule classes for HCL2 tuples, objects, and their elements."""

from typing import Tuple, List, Optional, Union, Any

from hcl2.rules.abstract import LarkRule
from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.literal_rules import (
    FloatLitRule,
    IntLitRule,
    IdentifierRule,
)
from hcl2.rules.strings import StringRule
from hcl2.rules.tokens import (
    COLON,
    EQ,
    LBRACE,
    COMMA,
    RBRACE,
    LSQB,
    RSQB,
    LPAR,
    RPAR,
    DOT,
)
from hcl2.rules.whitespace import (
    NewLineOrCommentRule,
    InlineCommentMixIn,
)
from hcl2.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
)


class TupleRule(InlineCommentMixIn):
    """Rule for tuple/array literals ([elem, ...])."""

    _children_layout: Tuple[
        LSQB,
        Optional[NewLineOrCommentRule],
        Tuple[
            ExpressionRule,
            Optional[NewLineOrCommentRule],
            COMMA,
            Optional[NewLineOrCommentRule],
            # ...
        ],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        Optional[COMMA],
        Optional[NewLineOrCommentRule],
        RSQB,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "tuple"

    @property
    def elements(self) -> List[ExpressionRule]:
        """Return the expression elements of the tuple."""
        return [
            child for child in self.children[1:-1] if isinstance(child, ExpressionRule)
        ]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a Python list or bracketed string."""
        if not options.wrap_tuples and not context.inside_dollar_string:
            return [element.serialize(options, context) for element in self.elements]

        with context.modify(inside_dollar_string=True):
            result = "["
            result += ", ".join(
                str(element.serialize(options, context)) for element in self.elements
            )
            result += "]"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)

        return result


class ObjectElemKeyRule(LarkRule):
    """Rule for an object element key."""

    key_T = Union[FloatLitRule, IntLitRule, IdentifierRule, StringRule]

    _children_layout: Tuple[key_T]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "object_elem_key"

    @property
    def value(self) -> key_T:
        """Return the key value (identifier, string, or number)."""
        return self._children[0]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize the key, coercing numbers to strings."""
        result = self.value.serialize(options, context)
        # Object keys must be strings for JSON compatibility
        if isinstance(result, (int, float)):
            result = str(result)
        return result


class ObjectElemKeyExpressionRule(LarkRule):
    """Rule for parenthesized expression keys in objects."""

    _children_layout: Tuple[
        LPAR,
        ExpressionRule,
        RPAR,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "object_elem_key_expression"

    @property
    def expression(self) -> ExpressionRule:
        """Return the parenthesized key expression."""
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to '(expression)' string."""
        with context.modify(inside_dollar_string=True):
            result = f"({self.expression.serialize(options, context)})"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class ObjectElemKeyDotAccessor(LarkRule):
    """Rule for dot-accessor keys in objects (e.g. a.b.c)."""

    _children_layout: Tuple[
        IdentifierRule,
        Tuple[
            IdentifierRule,
            DOT,
        ],
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "object_elem_key_dot_accessor"

    @property
    def identifiers(self) -> List[IdentifierRule]:
        """Return the chain of identifiers."""
        return [child for child in self._children if isinstance(child, IdentifierRule)]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'a.b.c' string."""
        return ".".join(
            identifier.serialize(options, context) for identifier in self.identifiers
        )


class ObjectElemRule(LarkRule):
    """Rule for a single key = value element in an object."""

    _children_layout: Tuple[
        ObjectElemKeyRule,
        Union[EQ, COLON],
        ExpressionRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "object_elem"

    @property
    def key(self) -> ObjectElemKeyRule:
        """Return the key rule."""
        return self._children[0]

    @property
    def expression(self):
        """Return the value expression."""
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a single-entry dict."""
        return {
            self.key.serialize(options, context): self.expression.serialize(
                options, context
            )
        }


class ObjectRule(InlineCommentMixIn):
    """Rule for object literals ({key = value, ...})."""

    _children_layout: Tuple[
        LBRACE,
        Optional[NewLineOrCommentRule],
        Tuple[
            ObjectElemRule,
            Optional[NewLineOrCommentRule],
            Optional[COMMA],
            Optional[NewLineOrCommentRule],
        ],
        RBRACE,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "object"

    @property
    def elements(self) -> List[ObjectElemRule]:
        """Return the list of object element rules."""
        return [
            child for child in self.children[1:-1] if isinstance(child, ObjectElemRule)
        ]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a Python dict or braced string."""
        if not options.wrap_objects and not context.inside_dollar_string:
            dict_result: dict = {}
            for element in self.elements:
                dict_result.update(element.serialize(options, context))
            return dict_result

        with context.modify(inside_dollar_string=True):
            str_result = "{"
            str_result += ", ".join(
                f"{element.key.serialize(options, context)}"
                f" = "
                f"{element.expression.serialize(options, context)}"
                for element in self.elements
            )
            str_result += "}"

        if not context.inside_dollar_string:
            str_result = to_dollar_string(str_result)
        return str_result
