from typing import Optional, List, Any

from hcl2.rule_transformer.rules.abstract import TokenSequence, LarkToken, LarkRule
from hcl2.rule_transformer.utils import SerializationOptions


class NewLineOrCommentRule(LarkRule):

    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "new_line_or_comment"

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return TokenSequence(self._children).serialize(options)

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
