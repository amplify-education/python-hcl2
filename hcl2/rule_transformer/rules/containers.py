from typing import Tuple, List, Optional, Union, Any

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expression import Expression
from hcl2.rule_transformer.rules.literal_rules import (
    FloatLitRule,
    IntLitRule,
    IdentifierRule,
)
from hcl2.rule_transformer.rules.strings import StringRule
from hcl2.rule_transformer.rules.tokens import (
    COLON_TOKEN,
    EQ_TOKEN,
    LBRACE_TOKEN,
    COMMA_TOKEN,
    RBRACE_TOKEN,
)
from hcl2.rule_transformer.rules.whitespace import (
    NewLineOrCommentRule,
    InlineCommentMixIn,
)
from hcl2.rule_transformer.utils import SerializationOptions


class ObjectElemKeyRule(LarkRule):
    _children: Tuple[Union[FloatLitRule, IntLitRule, IdentifierRule, StringRule]]

    @staticmethod
    def lark_name() -> str:
        return "object_elem_key"

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return self.children[0].serialize(options)


class ObjectElemRule(LarkRule):

    _children: Tuple[
        ObjectElemKeyRule,
        Union[EQ_TOKEN, COLON_TOKEN],
        Expression,
    ]

    @staticmethod
    def lark_name() -> str:
        return "object_elem"

    @property
    def key(self) -> ObjectElemKeyRule:
        return self.children[0]

    @property
    def expression(self):
        return self.children[2]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return {
            self.children[0].serialize(options): self.children[2].serialize(options)
        }


class ObjectRule(InlineCommentMixIn):

    _children: Tuple[
        LBRACE_TOKEN,
        Optional[NewLineOrCommentRule],
        Tuple[Union[ObjectElemRule, Optional[COMMA_TOKEN], NewLineOrCommentRule], ...],
        RBRACE_TOKEN,
    ]

    @staticmethod
    def lark_name() -> str:
        return "object"

    @property
    def elements(self) -> List[ObjectElemRule]:
        return [
            child for child in self.children[1:-1] if isinstance(child, ObjectElemRule)
        ]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        result = {}
        for element in self.elements:
            result.update(element.serialize())
        return result
