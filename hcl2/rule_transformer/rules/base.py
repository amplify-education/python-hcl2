from collections import defaultdict
from typing import Tuple, Any, List, Union, Optional

from lark.tree import Meta

from hcl2.const import IS_BLOCK
from hcl2.rule_transformer.rules.abstract import LarkRule, LarkToken
from hcl2.rule_transformer.rules.expressions import ExpressionRule, ExprTermRule
from hcl2.rule_transformer.rules.literal_rules import IdentifierRule
from hcl2.rule_transformer.rules.strings import StringRule
from hcl2.rule_transformer.rules.tokens import NAME, EQ, LBRACE, RBRACE

from hcl2.rule_transformer.rules.whitespace import NewLineOrCommentRule
from hcl2.rule_transformer.utils import SerializationOptions, SerializationContext


class AttributeRule(LarkRule):
    _children: Tuple[
        IdentifierRule,
        EQ,
        ExprTermRule,
    ]

    @staticmethod
    def lark_name() -> str:
        return "attribute"

    @property
    def identifier(self) -> IdentifierRule:
        return self._children[0]

    @property
    def expression(self) -> ExprTermRule:
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return {self.identifier.serialize(options): self.expression.serialize(options)}


class BodyRule(LarkRule):

    _children: List[
        Union[
            NewLineOrCommentRule,
            AttributeRule,
            "BlockRule",
        ]
    ]

    @staticmethod
    def lark_name() -> str:
        return "body"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        attribute_names = set()
        comments = []
        inline_comments = []

        result = defaultdict(list)

        for child in self._children:

            if isinstance(child, BlockRule):
                name = child.labels[0].serialize(options)
                if name in attribute_names:
                    raise RuntimeError(f"Attribute {name} is already defined.")
                result[name].append(child.serialize(options))

            if isinstance(child, AttributeRule):
                attribute_names.add(child)
                result.update(child.serialize(options))
                if options.with_comments:
                    # collect in-line comments from attribute assignments, expressions etc
                    inline_comments.extend(child.expression.inline_comments())

            if isinstance(child, NewLineOrCommentRule) and options.with_comments:
                child_comments = child.to_list()
                if child_comments:
                    comments.extend(child_comments)

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

    @staticmethod
    def lark_name() -> str:
        return "start"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return self.body.serialize(options)


class BlockRule(LarkRule):

    _children: Tuple[
        IdentifierRule,
        Optional[Union[IdentifierRule, StringRule]],
        LBRACE,
        BodyRule,
        RBRACE,
    ]

    def __init__(self, children, meta: Optional[Meta] = None):
        super().__init__(children, meta)

        *self._labels, self._body = [
            child for child in children if not isinstance(child, LarkToken)
        ]

    @staticmethod
    def lark_name() -> str:
        return "block"

    @property
    def labels(self) -> List[NAME]:
        return list(filter(lambda label: label is not None, self._labels))

    @property
    def body(self) -> BodyRule:
        return self._body

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        result = self._body.serialize(options)
        if options.explicit_blocks:
            result.update({IS_BLOCK: True})

        labels = self._labels
        for label in reversed(labels[1:]):
            result = {label.serialize(options): result}

        return result
