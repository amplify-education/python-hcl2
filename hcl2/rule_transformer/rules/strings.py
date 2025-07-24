from typing import Tuple, Optional, List, Any, Union

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expressions import ExpressionRule, ExprTermRule
from hcl2.rule_transformer.rules.literal_rules import StringPartRule
from hcl2.rule_transformer.rules.tokens import (
    INTERP_START,
    RBRACE,
    DBLQUOTE,
    STRING_CHARS,
)
from hcl2.rule_transformer.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
)


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
