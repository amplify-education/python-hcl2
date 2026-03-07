"""Rule classes for HCL2 structural elements (attributes, bodies, blocks)."""

from collections import defaultdict
from typing import Tuple, Any, List, Union, Optional

from lark.tree import Meta

from hcl2.const import IS_BLOCK
from hcl2.rules.abstract import LarkRule, LarkToken
from hcl2.rules.expressions import ExprTermRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.strings import StringRule
from hcl2.rules.tokens import EQ, LBRACE, RBRACE

from hcl2.rules.whitespace import NewLineOrCommentRule
from hcl2.utils import SerializationOptions, SerializationContext


class AttributeRule(LarkRule):
    """Rule for key = value attribute assignments."""

    _children_layout: Tuple[
        IdentifierRule,
        EQ,
        ExprTermRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "attribute"

    @property
    def identifier(self) -> IdentifierRule:
        """Return the attribute name identifier."""
        return self._children[0]

    @property
    def expression(self) -> ExprTermRule:
        """Return the attribute value expression."""
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a single-entry dict."""
        return {self.identifier.serialize(options): self.expression.serialize(options)}


class BodyRule(LarkRule):
    """Rule for a body containing attributes, blocks, and comments."""

    _children_layout: List[
        Union[
            NewLineOrCommentRule,
            AttributeRule,
            "BlockRule",
        ]
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "body"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a dict, grouping blocks under their type name."""
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
    """Rule for the top-level start rule of an HCL2 document."""

    _children_layout: Tuple[BodyRule]

    @property
    def body(self) -> BodyRule:
        """Return the document body."""
        return self._children[0]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "start"

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize by delegating to the body."""
        return self.body.serialize(options)


class BlockRule(LarkRule):
    """Rule for HCL2 blocks (e.g. resource 'type' 'name' { ... })."""

    _children_layout: Tuple[
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
        """Return the grammar rule name."""
        return "block"

    @property
    def labels(self) -> List[Union[IdentifierRule, StringRule]]:
        """Return the block label chain (type name, optional string labels)."""
        return list(filter(lambda label: label is not None, self._labels))

    @property
    def body(self) -> BodyRule:
        """Return the block body."""
        return self._body

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a nested dict with labels as keys."""
        result = self._body.serialize(options)
        if options.explicit_blocks:
            result.update({IS_BLOCK: True})

        labels = self._labels
        for label in reversed(labels[1:]):
            result = {label.serialize(options): result}

        return result
