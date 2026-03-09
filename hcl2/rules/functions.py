"""Rule classes for HCL2 function calls and arguments."""

from typing import Any, Optional, Tuple, Union, List

from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import COMMA, ELLIPSIS, StringToken, LPAR, RPAR
from hcl2.rules.whitespace import (
    InlineCommentMixIn,
    NewLineOrCommentRule,
)
from hcl2.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
)


class ArgumentsRule(InlineCommentMixIn):
    """Rule for a comma-separated list of function arguments."""

    _children_layout: Tuple[
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
        """Return the grammar rule name."""
        return "arguments"

    @property
    def has_ellipsis(self) -> bool:
        """Return whether the argument list ends with an ellipsis (...)."""
        for child in self._children[-2:]:
            if isinstance(child, StringToken) and child.lark_name() == "ELLIPSIS":
                return True
        return False

    @property
    def arguments(self) -> List[ExpressionRule]:
        """Return the list of expression arguments."""
        return [child for child in self._children if isinstance(child, ExpressionRule)]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to a comma-separated argument string."""
        result = ", ".join(
            str(argument.serialize(options, context)) for argument in self.arguments
        )
        if self.has_ellipsis:
            result += " ..."
        return result


class FunctionCallRule(InlineCommentMixIn):
    """Rule for function call expressions (e.g. func(args))."""

    _children_layout: Tuple[
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
        """Return the grammar rule name."""
        return "function_call"

    @property
    def identifiers(self) -> List[IdentifierRule]:
        """Return the function name identifier(s)."""
        return [child for child in self._children if isinstance(child, IdentifierRule)]

    @property
    def arguments(self) -> Optional[ArgumentsRule]:
        """Return the arguments rule, or None if no arguments."""
        for child in self._children:
            if isinstance(child, ArgumentsRule):
                return child
        return None

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'func(args)' string."""
        with context.modify(inside_dollar_string=True):
            name = "::".join(
                identifier.serialize(options, context)
                for identifier in self.identifiers
            )
            args = self.arguments
            args_str = args.serialize(options, context) if args else ""
            result = f"{name}({args_str})"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)

        return result
