from abc import ABC
from typing import Optional, List, Any, Tuple

from hcl2.rule_transformer.rules.abstract import LarkToken, LarkRule
from hcl2.rule_transformer.rules.literal_rules import TokenRule
from hcl2.rule_transformer.utils import SerializationOptions, SerializationContext


class NewLineOrCommentRule(TokenRule):
    @staticmethod
    def lark_name() -> str:
        return "new_line_or_comment"

    @classmethod
    def from_string(cls, string: str) -> "NewLineOrCommentRule":
        return cls([LarkToken("NL_OR_COMMENT", string)])

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return self.token.serialize()

    def to_list(
        self, options: SerializationOptions = SerializationOptions()
    ) -> Optional[List[str]]:
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

                if comment.endswith("*/"):
                    comment = comment[:-2]

            if comment != "":
                result.append(comment.strip())

        return result


class InlineCommentMixIn(LarkRule, ABC):
    def _insert_optionals(self, children: List, indexes: List[int] = None):
        for index in indexes:
            try:
                child = children[index]
            except IndexError:
                children.insert(index, None)
            else:
                if not isinstance(child, NewLineOrCommentRule):
                    children.insert(index, None)

    def inline_comments(self):
        result = []
        for child in self._children:

            if isinstance(child, NewLineOrCommentRule):
                comments = child.to_list()
                if comments is not None:
                    result.extend(comments)

            elif isinstance(child, InlineCommentMixIn):
                result.extend(child.inline_comments())

        return result
