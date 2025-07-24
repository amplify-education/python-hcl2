from abc import ABC
from typing import Any, Tuple

from hcl2.rule_transformer.rules.abstract import LarkRule, LarkToken
from hcl2.rule_transformer.utils import SerializationOptions, SerializationContext


class TokenRule(LarkRule, ABC):

    _children: Tuple[LarkToken]

    @property
    def token(self) -> LarkToken:
        return self._children[0]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return self.token.serialize()


class KeywordRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "keyword"


class IdentifierRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "identifier"


class IntLitRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "int_lit"


class FloatLitRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "float_lit"


class StringPartRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "string_part"


class BinaryOperatorRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "binary_operator"
