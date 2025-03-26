from typing import Tuple, Any, List, Union, Optional

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import LarkRule, EQ_Token
from hcl2.rule_transformer.rules.expression import Expression
from hcl2.rule_transformer.rules.token_sequence import IdentifierRule

from hcl2.rule_transformer.rules.whitespace import NewLineOrCommentRule


class AttributeRule(LarkRule):
    _children: Tuple[
        IdentifierRule,
        EQ_Token,
        Expression,
    ]

    @staticmethod
    def rule_name() -> str:
        return "attribute"

    @property
    def identifier(self) -> IdentifierRule:
        return self._children[0]

    @property
    def expression(self) -> Expression:
        return self._children[2]

    def serialize(self) -> Any:
        return {self.identifier.serialize(): self.expression.serialize()}


class BodyRule(LarkRule):

    _children: List[
        Union[
            NewLineOrCommentRule,
            AttributeRule,
            "BlockRule",
        ]
    ]

    @staticmethod
    def rule_name() -> str:
        return "body"

    def serialize(self) -> Any:
        blocks: List[BlockRule] = []
        attributes: List[AttributeRule] = []
        comments = []

        for child in self._children:
            if isinstance(child, BlockRule):
                blocks.append(child)
            if isinstance(child, AttributeRule):
                attributes.append(child)
            if isinstance(child, NewLineOrCommentRule):
                child_comments = child.actual_comments()
                if child_comments:
                    comments.extend(child_comments)

        result = {}

        for attribute in attributes:
            result.update(
                {attribute.identifier.serialize(): attribute.expression.serialize()}
            )

        result.update(
            {block.labels[0].serialize(): block.serialize() for block in blocks}
        )

        if comments:
            result["__comments__"] = comments

        return result


class StartRule(LarkRule):

    _children: Tuple[BodyRule]

    @staticmethod
    def rule_name() -> str:
        return "start"

    @property
    def body(self) -> BodyRule:
        return self._children[0]

    def serialize(self) -> Any:
        return self.body.serialize()


class BlockRule(LarkRule):

    _children: Tuple[BodyRule]

    @staticmethod
    def rule_name() -> str:
        return "block"

    def __init__(self, children, meta: Optional[Meta] = None):
        super().__init__(children)
        *self._labels, self._body = children

    @property
    def labels(self) -> List[IdentifierRule]:
        return list(filter(lambda label: label is not None, self._labels))

    @property
    def body(self) -> BodyRule:
        return self._body

    def serialize(self) -> BodyRule:
        result = self._body.serialize()
        labels = self._labels
        for label in reversed(labels[1:]):
            result = {label.serialize(): result}
        return result
