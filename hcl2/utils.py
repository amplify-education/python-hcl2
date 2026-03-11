"""Serialization options, context tracking, and string utility helpers."""
import re
from contextlib import contextmanager
from dataclasses import dataclass, replace

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
