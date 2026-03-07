"""Token classes for terminal elements in the LarkElement tree."""

from functools import lru_cache
from typing import Callable, Any, Dict, Type, Optional, Tuple, Union

from hcl2.rules.abstract import LarkToken


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
        """Return a cached subclass keyed by the given grammar token name."""
        if not isinstance(name, str):
            raise TypeError("StringToken[...] expects a single str argument")
        return cls.__build_subclass(name)

    def __init__(self, value: Optional[Union[str, int, float]] = None):
        super().__init__(value)  # type: ignore[arg-type]

    @property
    def serialize_conversion(self) -> Callable[[Any], str]:
        """Return str as the conversion callable."""
        return str


class StaticStringToken(StringToken):
    """A StringToken subclass with a fixed default value set at class-creation time."""

    classes_by_value: Dict[Optional[str], Type["StringToken"]] = {}

    @classmethod
    @lru_cache(maxsize=None)
    def __build_subclass(
        cls, name: str, default_value: Optional[str] = None
    ) -> Type["StringToken"]:
        """Create a subclass with a constant `lark_name` and default value."""

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

    def __class_getitem__(  # type: ignore[override]
        cls, name: Tuple[str, str]
    ) -> Type["StringToken"]:
        """Return a cached subclass keyed by a (token_name, default_value) tuple."""
        token_name, default_value = name
        return cls.__build_subclass(token_name, default_value)

    def __init__(self):
        super().__init__(getattr(self, "_default_value"))

    @property
    def serialize_conversion(self) -> Callable[[Any], str]:
        """Return str as the conversion callable."""
        return str


# Explicitly define various kinds of string-based tokens for type hinting.
# mypy cannot follow the dynamic __class_getitem__ pattern, so every alias
# in this block carries a blanket ``type: ignore``.
# pylint: disable=invalid-name

# variable values
NAME = StringToken["NAME"]  # type: ignore
STRING_CHARS = StringToken["STRING_CHARS"]  # type: ignore
ESCAPED_INTERPOLATION = StringToken["ESCAPED_INTERPOLATION"]  # type: ignore
BINARY_OP = StringToken["BINARY_OP"]  # type: ignore
HEREDOC_TEMPLATE = StringToken["HEREDOC_TEMPLATE"]  # type: ignore
HEREDOC_TRIM_TEMPLATE = StringToken["HEREDOC_TRIM_TEMPLATE"]  # type: ignore
NL_OR_COMMENT = StringToken["NL_OR_COMMENT"]  # type: ignore
# static values
EQ = StaticStringToken[("EQ", "=")]  # type: ignore
COLON = StaticStringToken[("COLON", ":")]  # type: ignore
LPAR = StaticStringToken[("LPAR", "(")]  # type: ignore
RPAR = StaticStringToken[("RPAR", ")")]  # type: ignore
LBRACE = StaticStringToken[("LBRACE", "{")]  # type: ignore
RBRACE = StaticStringToken[("RBRACE", "}")]  # type: ignore
DOT = StaticStringToken[("DOT", ".")]  # type: ignore
COMMA = StaticStringToken[("COMMA", ",")]  # type: ignore
ELLIPSIS = StaticStringToken[("ELLIPSIS", "...")]  # type: ignore
QMARK = StaticStringToken[("QMARK", "?")]  # type: ignore
LSQB = StaticStringToken[("LSQB", "[")]  # type: ignore
RSQB = StaticStringToken[("RSQB", "]")]  # type: ignore
INTERP_START = StaticStringToken[("INTERP_START", "${")]  # type: ignore
DBLQUOTE = StaticStringToken[("DBLQUOTE", '"')]  # type: ignore
ATTR_SPLAT = StaticStringToken[("ATTR_SPLAT", ".*")]  # type: ignore
FULL_SPLAT = StaticStringToken[("FULL_SPLAT", "[*]")]  # type: ignore
FOR = StaticStringToken[("FOR", "for")]  # type: ignore
IN = StaticStringToken[("IN", "in")]  # type: ignore
IF = StaticStringToken[("IF", "if")]  # type: ignore
FOR_OBJECT_ARROW = StaticStringToken[("FOR_OBJECT_ARROW", "=>")]  # type: ignore

# pylint: enable=invalid-name


class IntLiteral(LarkToken):
    """Token for integer literal values."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar token name."""
        return "INT_LITERAL"

    @property
    def serialize_conversion(self) -> Callable:
        """Return int as the conversion callable."""
        return int


class FloatLiteral(LarkToken):
    """Token for floating-point literal values."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar token name."""
        return "FLOAT_LITERAL"

    @property
    def serialize_conversion(self) -> Callable:
        """Return float as the conversion callable."""
        return float
