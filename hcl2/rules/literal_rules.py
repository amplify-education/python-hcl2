from abc import ABC
from typing import Any, Tuple

from hcl2.rules.abstract import LarkRule, LarkToken
from hcl2.utils import SerializationOptions, SerializationContext, to_dollar_string


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

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        value = self.token.value
        # Scientific notation (e.g. 1.23e5) cannot survive a Python float()
        # round-trip, so preserve it as a ${...} expression string.
        if options.preserve_scientific_notation and isinstance(value, str) and "e" in value.lower():
            if context.inside_dollar_string:
                return value
            return to_dollar_string(value)
        return self.token.serialize()


class BinaryOperatorRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "binary_operator"
