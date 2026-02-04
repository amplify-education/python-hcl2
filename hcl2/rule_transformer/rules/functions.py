from functools import lru_cache
from typing import Any, Optional, Tuple, Union, List

from hcl2.rule_transformer.rules.expressions import ExpressionRule
from hcl2.rule_transformer.rules.literal_rules import IdentifierRule
from hcl2.rule_transformer.rules.tokens import COMMA, ELLIPSIS, StringToken, LPAR, RPAR
from hcl2.rule_transformer.rules.whitespace import (
    InlineCommentMixIn,
    NewLineOrCommentRule,
)
from hcl2.rule_transformer.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
)


class ArgumentsRule(InlineCommentMixIn):

    _children: Tuple[
        ExpressionRule,
        Tuple[
            Optional[NewLineOrCommentRule],
            COMMA,
            Optional[NewLineOrCommentRule],
            ExpressionRule,
            # ...
        ],
        Optional[Union[COMMA, ELLIPSIS]],
        Optional[NewLineOrCommentRule],
    ]

    @staticmethod
    def lark_name() -> str:
        return "arguments"

    @property
    @lru_cache(maxsize=None)
    def has_ellipsis(self) -> bool:
        for child in self._children[-2:]:
            if isinstance(child, StringToken) and child.lark_name() == "ELLIPSIS":
                return True
        return False

    @property
    def arguments(self) -> List[ExpressionRule]:
        return [child for child in self._children if isinstance(child, ExpressionRule)]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        result = ", ".join(
            [str(argument.serialize(options, context)) for argument in self.arguments]
        )
        if self.has_ellipsis:
            result += " ..."
        return result


class FunctionCallRule(InlineCommentMixIn):

    _children: Tuple[
        IdentifierRule,
        Optional[IdentifierRule],
        Optional[IdentifierRule],
        LPAR,
        Optional[NewLineOrCommentRule],
        Optional[ArgumentsRule],
        Optional[NewLineOrCommentRule],
        RPAR,
    ]

    @staticmethod
    def lark_name() -> str:
        return "function_call"

    @property
    @lru_cache(maxsize=None)
    def identifiers(self) -> List[IdentifierRule]:
        return [child for child in self._children if isinstance(child, IdentifierRule)]

    @property
    @lru_cache(maxsize=None)
    def arguments(self) -> Optional[ArgumentsRule]:
        for child in self._children[2:6]:
            if isinstance(child, ArgumentsRule):
                return child

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        with context.modify(inside_dollar_string=True):
            result = f"{'::'.join(identifier.serialize(options, context) for identifier in self.identifiers)}"
            result += f"({self.arguments.serialize(options, context) if self.arguments else ''})"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)

        return result


class ProviderFunctionCallRule(FunctionCallRule):
    _children: Tuple[
        IdentifierRule,
        IdentifierRule,
        IdentifierRule,
        LPAR,
        Optional[NewLineOrCommentRule],
        Optional[ArgumentsRule],
        Optional[NewLineOrCommentRule],
        RPAR,
    ]

    @staticmethod
    def lark_name() -> str:
        return "provider_function_call"
