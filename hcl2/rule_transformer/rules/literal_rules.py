from abc import ABC
from typing import Any, Tuple

from hcl2.rule_transformer.rules.abstract import LarkRule, LarkToken
from hcl2.rule_transformer.utils import SerializationOptions


class TokenRule(LarkRule, ABC):

    _children: Tuple[LarkToken]

    @property
    def token(self) -> LarkToken:
        return self._children[0]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return self.token.serialize()


class IdentifierRule(TokenRule):
    @property
    def lark_name(self) -> str:
        return "identifier"


class IntLitRule(TokenRule):
    @property
    def lark_name(self) -> str:
        return "int_lit"


class FloatLitRule(TokenRule):
    @property
    def lark_name(self) -> str:
        return "float_lit"


class StringPartRule(TokenRule):
    @property
    def lark_name(self) -> str:
        return "string"


class BinaryOperatorRule(TokenRule):
    @property
    def lark_name(self) -> str:
        return "binary_operator"
