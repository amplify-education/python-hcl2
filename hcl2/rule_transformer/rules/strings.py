from typing import Tuple, Optional, List, Any, Union

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expression import Expression, ExprTermRule
from hcl2.rule_transformer.rules.literal_rules import StringPartRule
from hcl2.rule_transformer.rules.tokens import (
    INTERP_START_TOKEN,
    RBRACE_TOKEN,
    DBLQUOTE_TOKEN,
    STRING_CHARS_TOKEN,
)
from hcl2.rule_transformer.utils import SerializationOptions


class StringRule(LarkRule):

    _children: Tuple[DBLQUOTE_TOKEN, List[StringPartRule], DBLQUOTE_TOKEN]

    @property
    def lark_name(self) -> str:
        return "string"

    @property
    def string_parts(self):
        return self.children[1:-1]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return '"' + "".join(part.serialize() for part in self.string_parts) + '"'


class InterpolationRule(LarkRule):

    _children: Tuple[
        INTERP_START_TOKEN,
        Expression,
        RBRACE_TOKEN,
    ]

    @property
    def lark_name(self) -> str:
        return "interpolation"

    @property
    def expression(self):
        return self.children[1]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return "${" + self.expression.serialize(options) + "}"
