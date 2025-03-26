from typing import Optional, List, Any

from hcl2.rule_transformer.rules.abstract import TokenSequence, LarkToken, LarkRule


class NewLineOrCommentRule(LarkRule):

    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "new_line_or_comment"

    def serialize(self) -> Any:
        return TokenSequence(self._children).joined()

    def actual_comments(self) -> Optional[List[str]]:
        comment = self.serialize()
        if comment == "\n":
            return None

        comment = comment.strip()
        comments = comment.split("\n")

        result = []
        for comment in comments:
            if comment.startswith("//"):
                comment = comment[2:]

            elif comment.startswith("#"):
                comment = comment[1:]

            if comment != "":
                result.append(comment.strip())

        return result
