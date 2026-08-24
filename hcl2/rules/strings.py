"""Rule classes for HCL2 string literals, interpolation, and heredoc templates."""

import re
import sys
from typing import Any, List, Tuple, Union

from hcl2.rules.abstract import LarkRule
from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.tokens import (
    DBLQUOTE,
    ESCAPED_DIRECTIVE,
    ESCAPED_INTERPOLATION,
    HEREDOC_TEMPLATE,
    HEREDOC_TRIM_TEMPLATE,
    INTERP_START,
    RBRACE,
    STRING_CHARS,
    TEMPLATE_STRING,
)
from hcl2.utils import (
    HEREDOC_PATTERN,
    HEREDOC_TRIM_PATTERN,
    SerializationContext,
    SerializationOptions,
    to_dollar_string,
)


def _strip_closing_marker_line(text: str) -> str:
    r"""Drop the closing marker line's indentation and the one newline before it.

    A heredoc body always ends ``...\n<indent>``, where ``<indent>`` is the
    whitespace preceding the closing marker on its own line. The spec allows
    "an arbitrary number of spaces preceding it", and neither that indentation
    nor the newline separating it from the last content line is part of the
    value. The newline may be ``\r\n``, since heredocs parse in CRLF files.

    Everything else is: additional blank lines, and trailing spaces on a
    content line. The latter are safe because a content line always ends with
    its own newline, so the indentation match never reaches them. This replaces
    a blanket ``rstrip("\n\t ")``, which could not tell the two apart and
    discarded both.
    """
    text = re.sub(r"[ \t]*\Z", "", text)
    return re.sub(r"\r?\n\Z", "", text)


class InterpolationRule(LarkRule):
    """Rule for ${expression} interpolation within strings."""

    _children_layout: Tuple[
        INTERP_START,
        ExpressionRule,
        RBRACE,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "interpolation"

    @property
    def expression(self):
        """Return the interpolated expression."""
        return self.children[1]

    def serialize(self, options=SerializationOptions(), context=SerializationContext()) -> Any:
        """Serialize to ${expression} string."""
        with context.modify(inside_dollar_string=True):
            return to_dollar_string(self.expression.serialize(options, context))


class StringPartRule(LarkRule):
    """Rule for a single part of a string (literal text, escape, interpolation, or directive)."""

    # Content may be a plain token (STRING_CHARS, ESCAPED_INTERPOLATION,
    # ESCAPED_DIRECTIVE), an InterpolationRule, or a template directive rule
    # (TemplateIfRule, TemplateForRule, and flat variants).  Forward refs are
    # quoted to avoid circular imports.
    _children_layout: Tuple[  # type: ignore[type-arg]
        Union[STRING_CHARS, ESCAPED_INTERPOLATION, ESCAPED_DIRECTIVE, InterpolationRule]
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "string_part"

    @property
    def content(self):
        """Return the content element (string chars, escape, interpolation, or directive)."""
        return self._children[0]

    def serialize(self, options=SerializationOptions(), context=SerializationContext()) -> Any:
        """Serialize this string part."""
        return self.content.serialize(options, context)


class StringRule(LarkRule):
    """Rule for quoted string literals."""

    _children_layout: Tuple[DBLQUOTE, List[StringPartRule], DBLQUOTE]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "string"

    @property
    def string_parts(self):
        """Return the list of string parts between quotes."""
        return self.children[1:-1]

    def serialize(self, options=SerializationOptions(), context=SerializationContext()) -> Any:
        """Serialize to a quoted string."""
        inner = "".join(part.serialize(options, context) for part in self.string_parts)
        if options.strip_string_quotes:
            return inner
        return '"' + inner + '"'


class HeredocTemplateRule(LarkRule):
    """Rule for heredoc template strings (<<MARKER)."""

    _children_layout: Tuple[HEREDOC_TEMPLATE]
    _trim_chars = "\n\t "

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "heredoc_template"

    @property
    def heredoc(self):
        """Return the raw heredoc token."""
        return self.children[0]

    def serialize(self, options=SerializationOptions(), context=SerializationContext()) -> Any:
        """Serialize the heredoc, optionally stripping to a plain string."""
        heredoc = self.heredoc.serialize(options, context)

        if not options.preserve_heredocs:
            match = HEREDOC_PATTERN.match(heredoc)
            if not match:
                raise RuntimeError(f"Invalid Heredoc token: {heredoc}")
            heredoc = _strip_closing_marker_line(match.group(2))
            heredoc = heredoc.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            if options.strip_string_quotes:
                return heredoc
            return f'"{heredoc}"'

        result = heredoc.rstrip(self._trim_chars)
        if options.strip_string_quotes:
            return result
        return f'"{result}"'


class HeredocTrimTemplateRule(HeredocTemplateRule):
    """Rule for indented heredoc template strings (<<-MARKER)."""

    _children_layout: Tuple[HEREDOC_TRIM_TEMPLATE]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "heredoc_template_trim"

    def serialize(self, options=SerializationOptions(), context=SerializationContext()) -> Any:
        """Serialize the trim heredoc, stripping common leading whitespace."""
        # See https://github.com/hashicorp/hcl2/blob/master/hcl/hclsyntax/spec.md#template-expressions
        # This is a special version of heredocs that are declared with "<<-"
        # This will calculate the minimum number of leading spaces in each line of a heredoc
        # and then remove that number of spaces from each line

        heredoc = self.heredoc.serialize(options, context)

        if not options.preserve_heredocs:
            match = HEREDOC_TRIM_PATTERN.match(heredoc)
            if not match:
                raise RuntimeError(f"Invalid Heredoc token: {heredoc}")
            heredoc = match.group(2)

        heredoc = _strip_closing_marker_line(heredoc)
        lines = heredoc.split("\n")

        # calculate the min number of leading spaces in each line
        # The spec measures "any literal string at the start of each line", so a
        # blank line offers no measurement. Counting it as zero would drag the
        # minimum down and cancel the dedent for every other line -- which only
        # became reachable once blank lines stopped being stripped above.
        min_spaces = sys.maxsize
        for line in lines:
            if not line.strip():
                continue
            leading_spaces = len(line) - len(line.lstrip(" "))
            min_spaces = min(min_spaces, leading_spaces)
        if min_spaces == sys.maxsize:
            min_spaces = 0

        # trim off that number of leading spaces from each line
        lines = [line[min_spaces:] for line in lines]

        if not options.preserve_heredocs:
            lines = [line.replace("\\", "\\\\").replace('"', '\\"') for line in lines]

        sep = "\\n" if not options.preserve_heredocs else "\n"
        inner = sep.join(lines)
        if options.strip_string_quotes:
            return inner
        return '"' + inner + '"'


class TemplateStringRule(LarkRule):
    """Rule for escaped-quote-delimited strings in template expressions (\\\"...\\\" )."""

    _children_layout: Tuple[TEMPLATE_STRING]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_string"

    @property
    def raw_value(self) -> str:
        """Return the raw token value including escaped quotes."""
        return str(self._children[0].value)

    @property
    def inner_value(self) -> str:
        """Return the string content without the escaped quote delimiters."""
        raw = self.raw_value
        # Strip leading \" and trailing \"
        if raw.startswith('\\"') and raw.endswith('\\"'):
            return raw[2:-2]
        return raw

    def serialize(self, options=SerializationOptions(), context=SerializationContext()) -> Any:
        """Serialize preserving escaped-quote delimiters for round-trip fidelity.

        Inside template directive expressions, strings are delimited by \\"
        rather than plain ". We preserve these as \\" in serialized form so
        the deserializer can reconstruct them correctly.
        """
        raw = self.raw_value
        if options.strip_string_quotes:
            return self.inner_value
        return raw
