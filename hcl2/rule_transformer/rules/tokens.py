from functools import lru_cache
from typing import Callable, Any, Type, Optional, Tuple

from hcl2.rule_transformer.rules.abstract import LarkToken


class StringToken(LarkToken):
    """
    Single run-time base class; every `StringToken["..."]` call returns a
    cached subclass whose static `lark_name()` yields the given string.
    """

    @classmethod
    @lru_cache(maxsize=None)
    def __build_subclass(cls, name: str) -> Type["StringToken"]:
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

    def __init__(self, value: Optional[Any] = None):
        super().__init__(value)

    @property
    def serialize_conversion(self) -> Callable[[Any], str]:
        return str


class StaticStringToken(LarkToken):

    classes_by_value = {}

    @classmethod
    @lru_cache(maxsize=None)
    def __build_subclass(
        cls, name: str, default_value: str = None
    ) -> Type["StringToken"]:
        """Create a subclass with a constant `lark_name`."""

        result = type(  # type: ignore
            f"{name}_TOKEN",
            (cls,),
            {
                "__slots__": (),
                "lark_name": staticmethod(lambda _n=name: _n),
                "_default_value": default_value,
            },
        )
        cls.classes_by_value[default_value] = result
        return result

    def __class_getitem__(cls, value: Tuple[str, str]) -> Type["StringToken"]:
        name, default_value = value
        return cls.__build_subclass(name, default_value)

    def __init__(self):
        super().__init__(getattr(self, "_default_value"))

    @property
    def serialize_conversion(self) -> Callable[[Any], str]:
        return str


# explicitly define various kinds of string-based tokens for type hinting
# variable values
NAME = StringToken["NAME"]
STRING_CHARS = StringToken["STRING_CHARS"]
ESCAPED_INTERPOLATION = StringToken["ESCAPED_INTERPOLATION"]
BINARY_OP = StringToken["BINARY_OP"]
HEREDOC_TEMPLATE = StringToken["HEREDOC_TEMPLATE"]
HEREDOC_TRIM_TEMPLATE = StringToken["HEREDOC_TRIM_TEMPLATE"]
NL_OR_COMMENT = StringToken["NL_OR_COMMENT"]
# static values
EQ = StaticStringToken[("EQ", "=")]
COLON = StaticStringToken[("COLON", ":")]
LPAR = StaticStringToken[("LPAR", "(")]
RPAR = StaticStringToken[("RPAR", ")")]
LBRACE = StaticStringToken[("LBRACE", "{")]
RBRACE = StaticStringToken[("RBRACE", "}")]
DOT = StaticStringToken[("DOT", ".")]
COMMA = StaticStringToken[("COMMA", ",")]
ELLIPSIS = StaticStringToken[("ELLIPSIS", "...")]
QMARK = StaticStringToken[("QMARK", "?")]
LSQB = StaticStringToken[("LSQB", "[")]
RSQB = StaticStringToken[("RSQB", "]")]
INTERP_START = StaticStringToken[("INTERP_START", "${")]
DBLQUOTE = StaticStringToken[("DBLQUOTE", '"')]
ATTR_SPLAT = StaticStringToken[("ATTR_SPLAT", ".*")]
FULL_SPLAT = StaticStringToken[("FULL_SPLAT", "[*]")]
FOR = StaticStringToken[("FOR", "for")]
IN = StaticStringToken[("IN", "in")]
IF = StaticStringToken[("IF", "if")]
FOR_OBJECT_ARROW = StaticStringToken[("FOR_OBJECT_ARROW", "=>")]


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
