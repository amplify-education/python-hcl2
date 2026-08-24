"""Serialization options, context tracking, and string utility helpers."""

import re
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Optional, Tuple

HEREDOC_PATTERN = re.compile(r"<<([a-zA-Z][a-zA-Z0-9._-]+)\n([\s\S]*)\1", re.S)
HEREDOC_TRIM_PATTERN = re.compile(r"<<-([a-zA-Z][a-zA-Z0-9._-]+)\n([\s\S]*)\1", re.S)


@dataclass
class SerializationOptions:
    """Options controlling how LarkElement trees are serialized to Python dicts."""

    # Include __comments__ and __inline_comments__ keys in the output.
    with_comments: bool = True
    # Add __start_line__ and __end_line__ metadata to each block/attribute.
    with_meta: bool = False
    # Serialize nested objects as inline HCL strings (e.g. "${{key = value}}")
    # instead of Python dicts.
    wrap_objects: bool = False
    # Serialize tuples as inline HCL strings (e.g. "${[1, 2, 3]}")
    # instead of Python lists.
    wrap_tuples: bool = False
    # Add __is_block__ markers to distinguish blocks from plain objects.
    # Note: round-trip through from_dict/dumps is NOT supported WITHOUT this option.
    explicit_blocks: bool = True
    # Keep heredoc syntax (<<EOF...EOF) in output. When False, heredocs are
    # converted to regular escaped strings.
    preserve_heredocs: bool = True
    # Wrap all binary/unary operations in parentheses for explicit precedence.
    force_operation_parentheses: bool = False
    # Keep scientific notation for floats (e.g. 1e10). When False, expand to
    # standard decimal form.
    preserve_scientific_notation: bool = True
    # Remove surrounding double-quotes from serialized string values,
    # producing backwards-compatible output (e.g. "hello" instead of '"hello"').
    # Note: round-trip through from_dict/dumps is NOT supported WITH this option.
    strip_string_quotes: bool = False


_SIMPLE_ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    '"': '"',
    "\\": "\\",
}
_UNICODE_ESCAPE_WIDTHS = {"u": 4, "U": 8}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_MAX_CODEPOINT = 0x10FFFF
_SURROGATES = range(0xD800, 0xE000)


def _decode_unicode_escape(text: str, index: int) -> Optional[Tuple[str, int]]:
    """Decode a \\uNNNN or \\UNNNNNNNN escape whose marker sits at `index`.

    Returns None for anything that is not a usable character, leaving the
    caller to preserve the escape verbatim: too few digits, a non-hex digit, a
    codepoint past the Unicode maximum (`chr` raises for those), or a lone
    surrogate, which `chr` accepts but which cannot be encoded to UTF-8.
    """
    width = _UNICODE_ESCAPE_WIDTHS[text[index]]
    digits = text[index + 1 : index + 1 + width]
    if len(digits) != width or any(char not in _HEX_DIGITS for char in digits):
        return None
    codepoint = int(digits, 16)
    if codepoint > _MAX_CODEPOINT or codepoint in _SURROGATES:
        return None
    return chr(codepoint), index + 1 + width


def process_escape_sequences(value: str) -> str:
    """Resolve the escape sequences HCL defines inside a quoted template.

    Used when `strip_string_quotes` is set, which asks for the *value* of a
    string rather than its source form. Escapes are resolved in a single pass,
    so an escaped backslash cannot combine with the character after it: `\\\\n`
    is a backslash followed by "n", not a newline.

    An unrecognized escape is preserved verbatim, backslash included. Terraform
    rejects those outright, but the grammar here accepts them, and a serializer
    is the wrong place to raise an error the parser did not.
    """
    if "\\" not in value:
        return value

    parts = []
    index = 0
    length = len(value)
    while index < length:
        char = value[index]
        if char != "\\" or index + 1 >= length:
            parts.append(char)
            index += 1
            continue

        marker = value[index + 1]
        if marker in _SIMPLE_ESCAPES:
            parts.append(_SIMPLE_ESCAPES[marker])
            index += 2
            continue
        if marker in _UNICODE_ESCAPE_WIDTHS:
            decoded = _decode_unicode_escape(value, index + 1)
            if decoded is not None:
                parts.append(decoded[0])
                index = decoded[1]
                continue

        parts.append(char)
        parts.append(marker)
        index += 2

    return "".join(parts)


@dataclass
class SerializationContext:
    """Mutable state tracked during serialization traversal."""

    inside_dollar_string: bool = False
    inside_parentheses: bool = False

    def replace(self, **kwargs) -> "SerializationContext":
        """Return a new context with the given fields overridden."""
        return replace(self, **kwargs)

    @contextmanager
    def modify(self, **kwargs):
        """Context manager that temporarily mutates fields, restoring on exit."""
        original_values = {key: getattr(self, key) for key in kwargs}

        for key, value in kwargs.items():
            setattr(self, key, value)

        try:
            yield
        finally:
            # Restore original values
            for key, value in original_values.items():
                setattr(self, key, value)


def is_dollar_string(value: str) -> bool:
    """Return True if value is a ${...} interpolation wrapper."""
    if not isinstance(value, str):
        return False
    return value.startswith("${") and value.endswith("}")


def to_dollar_string(value: str) -> str:
    """Wrap value in ${...} if not already wrapped."""
    if not is_dollar_string(value):
        return f"${{{value}}}"
    return value


def unwrap_dollar_string(value: str) -> str:
    """Strip the ${...} wrapper from value if present."""
    if is_dollar_string(value):
        return value[2:-1]
    return value


def wrap_into_parentheses(value: str) -> str:
    """Wrap value in parentheses, preserving ${...} wrappers."""
    if is_dollar_string(value):
        value = unwrap_dollar_string(value)
        return to_dollar_string(f"({value})")
    return f"({value})"
