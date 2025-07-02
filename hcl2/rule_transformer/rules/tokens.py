from typing import Callable, Any

from hcl2.rule_transformer.rules.abstract import LarkToken


class StringToken(LarkToken):
    def __init__(self, name: str, value: Any):
        super().__init__(value)
        self._name = name

    @property
    def lark_name(self) -> str:
        return self._name

    @property
    def serialize_conversion(self) -> Callable:
        return str


# explicitly define various kinds of string-based tokens
STRING_CHARS_TOKEN = StringToken
ESCAPED_INTERPOLATION_TOKEN = StringToken
BINARY_OP_TOKEN = StringToken
EQ_TOKEN = StringToken
COLON_TOKEN = StringToken
LPAR_TOKEN = StringToken  # (
RPAR_TOKEN = StringToken  # )
LBRACE_TOKEN = StringToken  # {
RBRACE_TOKEN = StringToken  # }
DOT_TOKEN = StringToken
COMMA_TOKEN = StringToken
QMARK_TOKEN = StringToken
LSQB_TOKEN = StringToken  # [
RSQB_TOKEN = StringToken  # ]
INTERP_START_TOKEN = StringToken  # ${
DBLQUOTE_TOKEN = StringToken  # "


class IdentifierToken(LarkToken):
    @property
    def lark_name(self) -> str:
        return "IDENTIFIER"

    @property
    def serialize_conversion(self) -> Callable:
        return str


class IntToken(LarkToken):
    @property
    def lark_name(self) -> str:
        return "INT_LITERAL"

    @property
    def serialize_conversion(self) -> Callable:
        return int


class FloatToken(LarkToken):
    @property
    def lark_name(self) -> str:
        return "FLOAT_LITERAL"

    @property
    def serialize_conversion(self) -> Callable:
        return float
