"""Rule classes for whitespace, comments, and inline comment handling."""

from abc import ABC
from typing import Optional, List, Any

from hcl2.rules.abstract import LarkRule
from hcl2.rules.literal_rules import TokenRule
from hcl2.rules.tokens import NL_OR_COMMENT
from hcl2.utils import SerializationOptions, SerializationContext


class NewLineOrCommentRule(TokenRule):
    """Rule for newline and comment tokens."""

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "new_line_or_comment"

    @classmethod
    def from_string(cls, string: str) -> "NewLineOrCommentRule":
        """Create an instance from a raw comment or newline string."""
        return cls([NL_OR_COMMENT(string)])  # type: ignore[abstract]  # pylint: disable=abstract-class-instantiated

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to the raw comment/newline string."""
        return "".join(child.serialize() for child in self._children)

    @property
    def is_inline(self) -> bool:
        """True if this comment is on the same line as preceding code.

        A raw string starting with ``\\n`` means the comment sits on its own
        line (standalone).  One starting with ``#``, ``//``, or ``/*`` is
        inline — it follows code on the same line.
        """
        return not self.serialize().startswith("\n")

    def to_list(
        self, options: SerializationOptions = SerializationOptions()
    ) -> Optional[List[dict]]:
        """Extract comment objects, or None if only a newline."""
        raw = self.serialize(options)
        if raw == "\n":
            return None

        stripped = raw.strip()

        # Block comments: keep as a single value
        if stripped.startswith("/*") and stripped.endswith("*/"):
            text = stripped[2:-2].strip()
            if text:
                return [{"value": text}]
            return None

        # Line comments: one value per line
        result = []
        for line in raw.split("\n"):
            line = line.strip()

            for delimiter in ("//", "#"):
                if line.startswith(delimiter):
                    line = line[len(delimiter) :]
                    break

            if line != "":
                result.append({"value": line.strip()})

        return result


class InlineCommentMixIn(LarkRule, ABC):
    """Mixin for rules that may contain inline comments among their children."""

    def _insert_optionals(self, children: List, indexes: Optional[List[int]] = None):
        """Insert None placeholders at expected optional-child positions."""
        if indexes is None:
            return
        for index in indexes:
            try:
                child = children[index]
            except IndexError:
                children.insert(index, None)
            else:
                if not isinstance(child, NewLineOrCommentRule):
                    children.insert(index, None)

    def inline_comments(self):
        """Collect all inline comment strings from this rule's children."""
        result = []
        for child in self._children:

            if isinstance(child, NewLineOrCommentRule):
                comments = child.to_list()
                if comments is not None:
                    result.extend(comments)

            elif isinstance(child, InlineCommentMixIn):
                result.extend(child.inline_comments())

        return result

    def absorbed_comments(self):
        """Return body-level comments absorbed by grammar into this expression.

        Default: empty.  ``BinaryOpRule`` overrides this because its trailing
        ``new_line_or_comment?`` can swallow the next body-level comment.
        """
        return []
