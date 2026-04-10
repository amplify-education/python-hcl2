"""Rule classes for literal values (keywords, identifiers, numbers, operators)."""

from abc import ABC
from typing import Any, Tuple

from hcl2.rules.abstract import LarkRule, LarkToken
from hcl2.utils import SerializationOptions, SerializationContext, to_dollar_string


class TokenRule(LarkRule, ABC):
    """Base rule wrapping a single token child."""

    _children_layout: Tuple[LarkToken]

    @property
    def token(self) -> LarkToken:
        """Return the single token child."""
        return self._children[0]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize by delegating to the token's own serialization."""
        return self.token.serialize()


class KeywordRule(TokenRule):
    """Rule for HCL2 keyword literals (true, false, null)."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "keyword"


class LiteralValueRule(TokenRule):
    """Rule for HCL2 literal value keywords (true, false, null)."""

    _SERIALIZE_MAP = {"true": True, "false": False, "null": None}

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "literal_value"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to Python True, False, or None."""
        value = self.token.value
        if context.inside_dollar_string:
            return str(value)
        return self._SERIALIZE_MAP.get(str(value), str(value))


class IdentifierRule(TokenRule):
    """Rule for HCL2 identifiers."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "identifier"


class IntLitRule(TokenRule):
    """Rule for integer literal expressions."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "int_lit"


class FloatLitRule(TokenRule):
    """Rule for floating-point literal expressions."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "float_lit"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize, preserving scientific notation when configured."""
        value = self.token.value
        # Scientific notation (e.g. 1.23e5) cannot survive a Python float()
        # round-trip, so preserve it as a ${...} expression string.
        if (
            options.preserve_scientific_notation
            and isinstance(value, str)
            and "e" in value.lower()
        ):
            if context.inside_dollar_string:
                return value
            return to_dollar_string(value)
        return self.token.serialize()


class BinaryOperatorRule(TokenRule):
    """Rule for binary operator tokens."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "binary_operator"
