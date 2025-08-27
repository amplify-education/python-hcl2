import re
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Generator

HEREDOC_PATTERN = re.compile(r"<<([a-zA-Z][a-zA-Z0-9._-]+)\n([\s\S]*)\1", re.S)
HEREDOC_TRIM_PATTERN = re.compile(r"<<-([a-zA-Z][a-zA-Z0-9._-]+)\n([\s\S]*)\1", re.S)



@dataclass
class SerializationOptions:
    with_comments: bool = True
    with_meta: bool = False
    wrap_objects: bool = False
    wrap_tuples: bool = False
    explicit_blocks: bool = True
    preserve_heredocs: bool = True


@dataclass
class DeserializationOptions:
    heredocs_to_strings: bool = False


@dataclass
class SerializationContext:
    inside_dollar_string: bool = False

    def replace(self, **kwargs) -> "SerializationContext":
        return replace(self, **kwargs)

    @contextmanager
    def copy(self, **kwargs) -> Generator["SerializationContext", None, None]:
        """Context manager that yields a modified copy of the context"""
        modified_context = self.replace(**kwargs)
        yield modified_context

    @contextmanager
    def modify(self, **kwargs):
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
    if not isinstance(value, str):
        return False
    return value.startswith("${") and value.endswith("}")


def to_dollar_string(value: str) -> str:
    if not is_dollar_string(value):
        return f"${{{value}}}"
    return value


def unwrap_dollar_string(value: str) -> str:
    if is_dollar_string(value):
        return value[2:-1]
    return value


def wrap_into_parentheses(value: str) -> str:
    if is_dollar_string(value):
        value = unwrap_dollar_string(value)
        return to_dollar_string(f"({value})")
    return f"({value})"
