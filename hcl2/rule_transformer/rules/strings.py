from typing import Tuple, List, Any, Union

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expressions import ExpressionRule
from hcl2.rule_transformer.rules.tokens import (
    INTERP_START,
    RBRACE,
    DBLQUOTE,
    STRING_CHARS,
    ESCAPED_INTERPOLATION,
)
from hcl2.rule_transformer.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
)


class InterpolationRule(LarkRule):

    _children: Tuple[
        INTERP_START,
        ExpressionRule,
        RBRACE,
    ]

    @staticmethod
    def lark_name() -> str:
        return "interpolation"

    @property
    def expression(self):
        return self.children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return to_dollar_string(self.expression.serialize(options))


class StringPartRule(LarkRule):
    _children: Tuple[Union[STRING_CHARS, ESCAPED_INTERPOLATION, InterpolationRule]]

    @staticmethod
    def lark_name() -> str:
        return "string_part"

    @property
    def content(self) -> Union[STRING_CHARS, ESCAPED_INTERPOLATION, InterpolationRule]:
        return self._children[0]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return self.content.serialize(options, context)


class StringRule(LarkRule):

    _children: Tuple[DBLQUOTE, List[StringPartRule], DBLQUOTE]

    @staticmethod
    def lark_name() -> str:
        return "string"

    @property
    def string_parts(self):
        return self.children[1:-1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return '"' + "".join(part.serialize() for part in self.string_parts) + '"'
