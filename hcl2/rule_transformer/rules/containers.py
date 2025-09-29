import json
from typing import Tuple, List, Optional, Union, Any

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expressions import ExpressionRule
from hcl2.rule_transformer.rules.literal_rules import (
    FloatLitRule,
    IntLitRule,
    IdentifierRule,
)
from hcl2.rule_transformer.rules.strings import StringRule
from hcl2.rule_transformer.rules.tokens import (
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
from hcl2.rule_transformer.rules.whitespace import (
    NewLineOrCommentRule,
    InlineCommentMixIn,
)
from hcl2.rule_transformer.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
)


class TupleRule(InlineCommentMixIn):

    _children: Tuple[
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
        return "tuple"

    @property
    def elements(self) -> List[ExpressionRule]:
        return [
            child for child in self.children[1:-1] if isinstance(child, ExpressionRule)
        ]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
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

    key_T = Union[FloatLitRule, IntLitRule, IdentifierRule, StringRule]

    _children: Tuple[key_T]

    @staticmethod
    def lark_name() -> str:
        return "object_elem_key"

    @property
    def value(self) -> key_T:
        return self._children[0]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return self.value.serialize(options, context)


class ObjectElemKeyExpressionRule(LarkRule):

    _children: Tuple[
        LPAR,
        ExpressionRule,
        RPAR,
    ]

    @staticmethod
    def lark_name() -> str:
        return "object_elem_key_expression"

    @property
    def expression(self) -> ExpressionRule:
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        with context.modify(inside_dollar_string=True):
            result = f"({self.expression.serialize(options, context)})"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class ObjectElemKeyDotAccessor(LarkRule):

    _children: Tuple[
        IdentifierRule,
        Tuple[
            IdentifierRule,
            DOT,
        ],
    ]

    @staticmethod
    def lark_name() -> str:
        return "object_elem_key_dot_accessor"

    @property
    def identifiers(self) -> List[IdentifierRule]:
        return [child for child in self._children if isinstance(child, IdentifierRule)]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return ".".join(
            identifier.serialize(options, context) for identifier in self.identifiers
        )


class ObjectElemRule(LarkRule):

    _children: Tuple[
        ObjectElemKeyRule,
        Union[EQ, COLON],
        ExpressionRule,
    ]

    @staticmethod
    def lark_name() -> str:
        return "object_elem"

    @property
    def key(self) -> ObjectElemKeyRule:
        return self._children[0]

    @property
    def expression(self):
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return {
            self.key.serialize(options, context): self.expression.serialize(
                options, context
            )
        }


class ObjectRule(InlineCommentMixIn):

    _children: Tuple[
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
        return "object"

    @property
    def elements(self) -> List[ObjectElemRule]:
        return [
            child for child in self.children[1:-1] if isinstance(child, ObjectElemRule)
        ]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        if not options.wrap_objects and not context.inside_dollar_string:
            result = {}
            for element in self.elements:
                result.update(element.serialize(options, context))

            return result

        with context.modify(inside_dollar_string=True):
            result = "{"
            result += ", ".join(
                f"{element.key.serialize(options, context)} = {element.expression.serialize(options,context)}"
                for element in self.elements
            )
            result += "}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result
