from functools import lru_cache
from typing import Callable, Any, Type

from hcl2.rule_transformer.rules.abstract import LarkToken


class StringToken(LarkToken):
    """
    Single run-time base class; every `StringToken["..."]` call returns a
    cached subclass whose static `lark_name()` yields the given string.
    """

    @staticmethod
    @lru_cache(maxsize=None)
    def __build_subclass(name: str) -> Type["StringToken"]:
        """Create a subclass with a constant `lark_name`."""
        return type(  # type: ignore
            f"{name}_TOKEN",
            (StringToken,),
            {
                "__slots__": (),
                "lark_name": staticmethod(lambda _n=name: _n),
            },
        )

    def __class_getitem__(cls, name: str) -> Type["StringToken"]:
        if not isinstance(name, str):
            raise TypeError("StringToken[...] expects a single str argument")
        return cls.__build_subclass(name)

    def __init__(self, value: Any) -> None:
        super().__init__(value)

    @property
    def serialize_conversion(self) -> Callable[[Any], str]:
        return str


# explicitly define various kinds of string-based tokens for type hinting
NAME = StringToken["NAME"]
STRING_CHARS = StringToken["STRING_CHARS"]
ESCAPED_INTERPOLATION = StringToken["ESCAPED_INTERPOLATION"]
BINARY_OP = StringToken["BINARY_OP"]
EQ = StringToken["EQ"]
COLON = StringToken["COLON"]
LPAR = StringToken["LPAR"]
RPAR = StringToken["RPAR"]
LBRACE = StringToken["LBRACE"]
RBRACE = StringToken["RBRACE"]
DOT = StringToken["DOT"]
COMMA = StringToken["COMMA"]
ELLIPSIS = StringToken["ELLIPSIS"]
QMARK = StringToken["QMARK"]
LSQB = StringToken["LSQB"]
RSQB = StringToken["RSQB"]
INTERP_START = StringToken["INTERP_START"]
DBLQUOTE = StringToken["DBLQUOTE"]
ATTR_SPLAT = StringToken["ATTR_SPLAT"]
FULL_SPLAT = StringToken["FULL_SPLAT"]


class IntLiteral(LarkToken):
    @staticmethod
    def lark_name() -> str:
        return "INT_LITERAL"

    @property
    def serialize_conversion(self) -> Callable:
        return int


class FloatLiteral(LarkToken):
    @staticmethod
    def lark_name() -> str:
        return "FLOAT_LITERAL"

    @property
    def serialize_conversion(self) -> Callable:
        return float
