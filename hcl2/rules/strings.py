"""Rule classes for HCL2 string literals, interpolation, and heredoc templates."""

import sys
from typing import Tuple, List, Any, Union

from hcl2.rules.abstract import LarkRule
from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.tokens import (
    INTERP_START,
    RBRACE,
    DBLQUOTE,
    STRING_CHARS,
    ESCAPED_INTERPOLATION,
    HEREDOC_TEMPLATE,
    HEREDOC_TRIM_TEMPLATE,
)
from hcl2.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
    HEREDOC_TRIM_PATTERN,
    HEREDOC_PATTERN,
)


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

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to ${expression} string."""
        return to_dollar_string(self.expression.serialize(options, context))


class StringPartRule(LarkRule):
    """Rule for a single part of a string (literal text, escape, or interpolation)."""

    _children_layout: Tuple[
        Union[STRING_CHARS, ESCAPED_INTERPOLATION, InterpolationRule]
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "string_part"

    @property
    def content(self) -> Union[STRING_CHARS, ESCAPED_INTERPOLATION, InterpolationRule]:
        """Return the content element (string chars, escape, or interpolation)."""
        return self._children[0]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
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

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a quoted string."""
        return (
            '"'
            + "".join(part.serialize(options, context) for part in self.string_parts)
            + '"'
        )


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

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize the heredoc, optionally stripping to a plain string."""
        heredoc = self.heredoc.serialize(options, context)

        if not options.preserve_heredocs:
            match = HEREDOC_PATTERN.match(heredoc)
            if not match:
                raise RuntimeError(f"Invalid Heredoc token: {heredoc}")
            heredoc = match.group(2).rstrip(self._trim_chars)
            heredoc = (
                heredoc.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            )
            return f'"{heredoc}"'

        result = heredoc.rstrip(self._trim_chars)
        return f'"{result}"'


class HeredocTrimTemplateRule(HeredocTemplateRule):
    """Rule for indented heredoc template strings (<<-MARKER)."""

    _children_layout: Tuple[HEREDOC_TRIM_TEMPLATE]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "heredoc_template_trim"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
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

        heredoc = heredoc.rstrip(self._trim_chars)
        lines = heredoc.split("\n")

        # calculate the min number of leading spaces in each line
        min_spaces = sys.maxsize
        for line in lines:
            leading_spaces = len(line) - len(line.lstrip(" "))
            min_spaces = min(min_spaces, leading_spaces)

        # trim off that number of leading spaces from each line
        lines = [line[min_spaces:] for line in lines]

        if not options.preserve_heredocs:
            lines = [line.replace("\\", "\\\\").replace('"', '\\"') for line in lines]

        sep = "\\n" if not options.preserve_heredocs else "\n"
        return '"' + sep.join(lines) + '"'
