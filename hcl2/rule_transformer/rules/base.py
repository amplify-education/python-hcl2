from collections import defaultdict
from typing import Tuple, Any, List, Union, Optional

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import LarkRule, LarkToken
from hcl2.rule_transformer.rules.expression import Expression
from hcl2.rule_transformer.rules.tokens import IdentifierToken, EQ_TOKEN

from hcl2.rule_transformer.rules.whitespace import NewLineOrCommentRule
from hcl2.rule_transformer.utils import SerializationOptions


class AttributeRule(LarkRule):
    _children: Tuple[
        IdentifierToken,
        EQ_TOKEN,
        Expression,
    ]

    @property
    def lark_name(self) -> str:
        return "attribute"

    @property
    def identifier(self) -> IdentifierToken:
        return self._children[0]

    @property
    def expression(self) -> Expression:
        return self._children[2]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return {self.identifier.serialize(options): self.expression.serialize(options)}


class BodyRule(LarkRule):

    _children: List[
        Union[
            NewLineOrCommentRule,
            # AttributeRule,
            "BlockRule",
        ]
    ]

    @property
    def lark_name(self) -> str:
        return "body"

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        blocks: List[BlockRule] = []
        attributes: List[AttributeRule] = []
        comments = []
        inline_comments = []
        for child in self._children:

            if isinstance(child, BlockRule):
                blocks.append(child)

            if isinstance(child, AttributeRule):
                attributes.append(child)
                # collect in-line comments from attribute assignments, expressions etc
                inline_comments.extend(child.expression.inline_comments())

            if isinstance(child, NewLineOrCommentRule):
                child_comments = child.to_list()
                if child_comments:
                    comments.extend(child_comments)

        result = {}

        for attribute in attributes:
            result.update(attribute.serialize(options))

        result_blocks = defaultdict(list)
        for block in blocks:
            name = block.labels[0].serialize(options)
            if name in result.keys():
                raise RuntimeError(f"Attribute {name} is already defined.")
            result_blocks[name].append(block.serialize(options))

        result.update(**result_blocks)

        if options.with_comments:
            if comments:
                result["__comments__"] = comments
            if inline_comments:
                result["__inline_comments__"] = inline_comments

        return result


class StartRule(LarkRule):

    _children: Tuple[BodyRule]

    @property
    def body(self) -> BodyRule:
        return self._children[0]

    @property
    def lark_name(self) -> str:
        return "start"

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return self.body.serialize(options)


class BlockRule(LarkRule):

    _children: Tuple[BodyRule]

    def __init__(self, children, meta: Optional[Meta] = None):
        super().__init__(children, meta)

        *self._labels, self._body = [
            child for child in children if not isinstance(child, LarkToken)
        ]

    @property
    def lark_name(self) -> str:
        return "block"

    @property
    def labels(self) -> List[IdentifierToken]:
        return list(filter(lambda label: label is not None, self._labels))

    @property
    def body(self) -> BodyRule:
        return self._body

    def serialize(
        self, options: SerializationOptions = SerializationOptions()
    ) -> BodyRule:
        result = self._body.serialize(options)
        labels = self._labels
        for label in reversed(labels):
            result = {label.serialize(options): result}
        return result
