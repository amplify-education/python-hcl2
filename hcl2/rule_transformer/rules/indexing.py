from typing import List, Optional, Tuple, Any

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expression import ExprTermRule, Expression
from hcl2.rule_transformer.rules.tokens import (
    DOT_TOKEN,
    IntToken,
    LSQB_TOKEN,
    RSQB_TOKEN,
)
from hcl2.rule_transformer.rules.whitespace import (
    InlineCommentMixIn,
    NewLineOrCommentRule,
)
from hcl2.rule_transformer.utils import SerializationOptions, to_dollar_string


class ShortIndexRule(LarkRule):

    _children: Tuple[
        DOT_TOKEN,
        IntToken,
    ]

    @property
    def lark_name(self) -> str:
        return "short_index"

    @property
    def index(self):
        return self.children[1]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return f".{self.index.serialize(options)}"


class SqbIndex(InlineCommentMixIn):
    _children: Tuple[
        LSQB_TOKEN,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
        Optional[NewLineOrCommentRule],
        RSQB_TOKEN,
    ]

    @property
    def lark_name(self) -> str:
        return "braces_index"

    @property
    def index_expression(self):
        return self.children[2]

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return f"[{self.index_expression.serialize(options)}]"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._possibly_insert_null_comments(children, [1, 3])
        super().__init__(children, meta)


class IndexExprTermRule(Expression):

    _children: Tuple[ExprTermRule, SqbIndex]

    @property
    def lark_name(self) -> str:
        return "index_expr_term"

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return to_dollar_string(
            f"{self.children[0].serialize(options)}{self.children[1].serialize(options)}"
        )
