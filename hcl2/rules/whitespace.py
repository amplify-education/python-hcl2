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
        return self.token.serialize()

    def to_list(
        self, options: SerializationOptions = SerializationOptions()
    ) -> Optional[List[str]]:
        """Extract comment text strings, or None if only a newline."""
        comment = self.serialize(options)
        if comment == "\n":
            return None

        comments = comment.split("\n")

        result = []
        for comment in comments:
            comment = comment.strip()

            for delimiter in ("//", "/*", "#"):
                if comment.startswith(delimiter):
                    comment = comment[len(delimiter) :]
                    if delimiter == "/*" and comment.endswith("*/"):
                        comment = comment[:-2]
                    break

            if comment != "":
                result.append(comment.strip())

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
