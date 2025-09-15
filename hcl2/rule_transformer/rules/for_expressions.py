from typing import Any, Tuple, Optional, List

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import LarkRule, LarkElement
from hcl2.rule_transformer.rules.expressions import ExpressionRule
from hcl2.rule_transformer.rules.literal_rules import IdentifierRule
from hcl2.rule_transformer.rules.tokens import (
    LSQB,
    RSQB,
    LBRACE,
    RBRACE,
    FOR,
    IN,
    IF,
    COMMA,
    COLON,
    ELLIPSIS,
    FOR_OBJECT_ARROW,
)
from hcl2.rule_transformer.rules.whitespace import (
    NewLineOrCommentRule,
    InlineCommentMixIn,
)
from hcl2.rule_transformer.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
)


class ForIntroRule(InlineCommentMixIn):
    """Rule for the intro part of for expressions: 'for key, value in collection :'"""

    _children: Tuple[
        FOR,
        Optional[NewLineOrCommentRule],
        IdentifierRule,
        Optional[COMMA],
        Optional[IdentifierRule],
        Optional[NewLineOrCommentRule],
        IN,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        COLON,
        Optional[NewLineOrCommentRule],
    ]

    @staticmethod
    def lark_name() -> str:
        return "for_intro"

    def __init__(self, children, meta: Optional[Meta] = None):
        # Insert null comments at positions where they might be missing
        self._possibly_insert_null_second_identifier(children)
        self._possibly_insert_null_comments(children, [1, 5, 7, 9, 11])
        super().__init__(children, meta)

    def _possibly_insert_null_second_identifier(self, children: List[LarkRule]):
        second_identifier_present = (
            len([child for child in children if isinstance(child, IdentifierRule)]) == 2
        )
        if not second_identifier_present:
            children.insert(3, None)
            children.insert(4, None)

    @property
    def first_iterator(self) -> IdentifierRule:
        """Returns the first iterator"""
        return self._children[2]

    @property
    def second_iterator(self) -> Optional[IdentifierRule]:
        """Returns the second iterator or None if not present"""
        return self._children[4]

    @property
    def iterable(self) -> ExpressionRule:
        """Returns the collection expression being iterated over"""
        return self._children[8]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> str:
        result = "for "

        result += f"{self.first_iterator.serialize(options, context)}"
        if self.second_iterator:
            result += f", {self.second_iterator.serialize(options, context)}"

        result += f" in {self.iterable.serialize(options, context)} : "

        return result


class ForCondRule(InlineCommentMixIn):
    """Rule for the optional condition in for expressions: 'if condition'"""

    _children: Tuple[
        IF,
        Optional[NewLineOrCommentRule],
        ExpressionRule,  # condition expression
    ]

    @staticmethod
    def lark_name() -> str:
        return "for_cond"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._possibly_insert_null_comments(children, [1])
        super().__init__(children, meta)

    @property
    def condition_expr(self) -> ExpressionRule:
        """Returns the condition expression"""
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> str:
        return f"if {self.condition_expr.serialize(options, context)}"


class ForTupleExprRule(ExpressionRule):
    """Rule for tuple/array for expressions: [for item in items : expression]"""

    _children: Tuple[
        LSQB,
        Optional[NewLineOrCommentRule],
        ForIntroRule,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        Optional[ForCondRule],
        Optional[NewLineOrCommentRule],
        RSQB,
    ]

    @staticmethod
    def lark_name() -> str:
        return "for_tuple_expr"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._possibly_insert_null_comments(children, [1, 3, 5, 7])
        self._possibly_insert_null_condition(children)
        super().__init__(children, meta)

    def _possibly_insert_null_condition(self, children: List[LarkElement]):
        if not len([child for child in children if isinstance(child, ForCondRule)]):
            children.insert(6, None)

    @property
    def for_intro(self) -> ForIntroRule:
        """Returns the for intro rule"""
        return self._children[2]

    @property
    def value_expr(self) -> ExpressionRule:
        """Returns the value expression"""
        return self._children[4]

    @property
    def condition(self) -> Optional[ForCondRule]:
        """Returns the optional condition rule"""
        return self._children[6]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:

        result = "["

        with context.modify(inside_dollar_string=True):
            result += self.for_intro.serialize(options, context)
            result += self.value_expr.serialize(options, context)

            if self.condition is not None:
                result += f" {self.condition.serialize(options, context)}"

        result += "]"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result


class ForObjectExprRule(ExpressionRule):
    """Rule for object for expressions: {for key, value in items : key => value}"""

    _children: Tuple[
        LBRACE,
        Optional[NewLineOrCommentRule],
        ForIntroRule,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        FOR_OBJECT_ARROW,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        Optional[ELLIPSIS],
        Optional[NewLineOrCommentRule],
        Optional[ForCondRule],
        Optional[NewLineOrCommentRule],
        RBRACE,
    ]

    @staticmethod
    def lark_name() -> str:
        return "for_object_expr"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._possibly_insert_null_comments(children, [1, 3, 6, 8, 10, 12])
        self._possibly_insert_null_optionals(children)
        super().__init__(children, meta)

    def _possibly_insert_null_optionals(self, children: List[LarkElement]):
        has_ellipsis = False
        has_condition = False

        for child in children:
            # if not has_ellipsis and isinstance(child, ELLIPSIS):
            if (
                has_ellipsis is False
                and child is not None
                and child.lark_name() == ELLIPSIS.lark_name()
            ):
                has_ellipsis = True
            if not has_condition and isinstance(child, ForCondRule):
                has_condition = True

        if not has_ellipsis:
            children.insert(9, None)

        if not has_condition:
            children.insert(11, None)

    @property
    def for_intro(self) -> ForIntroRule:
        """Returns the for intro rule"""
        return self._children[2]

    @property
    def key_expr(self) -> ExpressionRule:
        """Returns the key expression"""
        return self._children[4]

    @property
    def value_expr(self) -> ExpressionRule:
        """Returns the value expression"""
        return self._children[7]

    @property
    def ellipsis(self) -> Optional[ELLIPSIS]:
        """Returns the optional ellipsis token"""
        return self._children[9]

    @property
    def condition(self) -> Optional[ForCondRule]:
        """Returns the optional condition rule"""
        return self._children[11]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        result = "{"
        with context.modify(inside_dollar_string=True):
            result += self.for_intro.serialize(options, context)
            result += f"{self.key_expr.serialize(options, context)} => "

            result += self.value_expr.serialize(
                SerializationOptions(wrap_objects=True), context
            )

            if self.ellipsis is not None:
                result += self.ellipsis.serialize(options, context)

            if self.condition is not None:
                result += f" {self.condition.serialize(options, context)}"

        result += "}"
        if not context.inside_dollar_string:
            result = to_dollar_string(result)
        return result
