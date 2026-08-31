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
    process_escape_sequences,
    to_dollar_string,
)


def _strip_closing_marker_indent(text: str) -> str:
    r"""Drop the whitespace indenting the closing marker on its own line.

    A heredoc body always ends ``...\n<indent>``, where ``<indent>`` is the
    whitespace preceding the closing marker. The spec allows "an arbitrary
    number of spaces preceding it", and that indentation is not part of the
    value.

    The newline before it *is*. The spec ends the template where the delimiter
    "subsequently appears again on a line of its own", so every content line,
    the last one included, is terminated by its own newline: ``<<EOT\nline\nEOT``
    is ``"line\n"``, which is what Terraform and OpenTofu evaluate it to.

    Trailing spaces on a content line survive too, because such a line always
    ends with its own newline, so the match above never reaches them. This
    replaced a blanket ``rstrip("\n\t ")``, which could tell none of these
    apart and discarded all of them.
    """
    return re.sub(r"[ \t]*\Z", "", text)


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
        """Serialize to a quoted string.

        `strip_string_quotes` asks for the string's value rather than its
        source form, so it applies only where a value is what the caller gets:
        a string nested inside an expression is part of that expression's text,
        and unquoting it there would produce something that is no longer valid
        HCL (`upper("x")` becoming `upper(x)`).
        """
        if options.strip_string_quotes and not context.inside_dollar_string:
            return "".join(
                self._serialize_part_as_value(part, options, context) for part in self.string_parts
            )

        inner = "".join(part.serialize(options, context) for part in self.string_parts)
        return '"' + inner + '"'

    @staticmethod
    def _serialize_part_as_value(part, options, context) -> str:
        """Serialize one part, resolving escapes in literal text only.

        Interpolations and escaped interpolation/directive markers are passed
        through untouched: their text is expression source, not literal
        content, so an escape inside them is not this string's to resolve.
        """
        serialized = part.serialize(options, context)
        if part.content.lark_name() == "STRING_CHARS":
            return process_escape_sequences(serialized)
        return serialized


class HeredocTemplateRule(LarkRule):
    """Rule for heredoc template strings (<<MARKER)."""

    _children_layout: Tuple[HEREDOC_TEMPLATE]
    # \r is trimmed alongside \n so a CRLF heredoc does not leave a stray
    # carriage return hanging off the closing marker.
    _trim_chars = "\r\n\t "

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
            heredoc = _strip_closing_marker_indent(match.group(2))
            if options.strip_string_quotes:
                # The caller asked for the value, so hand back the body as-is:
                # real newlines, no escaping. The escaping below exists only to
                # build the quoted-string *source* form returned otherwise.
                return heredoc
            heredoc = heredoc.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
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
        # This is a special version of heredocs that are declared with "<<-",
        # whose body is dedented by the smallest indent any of its lines carries.
        heredoc = self.heredoc.serialize(options, context)

        if not options.preserve_heredocs:
            match = HEREDOC_TRIM_PATTERN.match(heredoc)
            if not match:
                raise RuntimeError(f"Invalid Heredoc token: {heredoc}")
            lines = self._dedent(_strip_closing_marker_indent(match.group(2)))
            if options.strip_string_quotes:
                # The caller asked for the value: real newlines, no escaping.
                return "\n".join(lines)
            escaped = [line.replace("\\", "\\\\").replace('"', '\\"') for line in lines]
            return '"' + "\\n".join(escaped) + '"'

        result = heredoc.rstrip(self._trim_chars)
        if options.strip_string_quotes:
            return result
        return f'"{result}"'

    @staticmethod
    def _dedent(body: str) -> List[str]:
        """Split *body* into lines and remove the common leading whitespace."""
        lines = body.split("\n")

        # The margin is the smallest indent any content line carries.
        #
        # The spec measures "any literal string at the start of each line", so a
        # blank line offers no measurement. Counting it as zero would drag the
        # margin down and cancel the dedent for every other line.
        #
        # It also says "spaces", but the reference implementation does not read
        # that as narrowly: OpenTofu dedents a tab-indented `<<-` heredoc by one
        # tab per level. Measuring whitespace characters rather than spaces
        # alone matches it, and is identical to counting spaces on the
        # space-indented input that reading the letter of the spec would cover.
        margin = sys.maxsize
        for line in lines:
            if not line.strip():
                continue
            margin = min(margin, len(line) - len(line.lstrip()))
        if margin == sys.maxsize:
            margin = 0

        # A line that offered no measurement is left exactly as written --
        # OpenTofu keeps a six-space line inside a four-space heredoc at six
        # spaces rather than two.
        return [line[margin:] if line.strip() else line for line in lines]


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
