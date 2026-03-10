"""Rule classes for HCL2 expressions, conditionals, and binary/unary operations."""

from abc import ABC
from typing import Any, Optional, Tuple

from lark.tree import Meta

from hcl2.rules.abstract import (
    LarkToken,
)
from hcl2.rules.literal_rules import BinaryOperatorRule
from hcl2.rules.tokens import LPAR, RPAR, QMARK, COLON
from hcl2.rules.whitespace import (
    NewLineOrCommentRule,
    InlineCommentMixIn,
)
from hcl2.utils import (
    wrap_into_parentheses,
    to_dollar_string,
    SerializationOptions,
    SerializationContext,
)


class ExpressionRule(InlineCommentMixIn, ABC):
    """Base class for all HCL2 expression rules."""

    @staticmethod
    def lark_name() -> str:
        """?expression is transparent in Lark — subclasses must override."""
        raise NotImplementedError("ExpressionRule.lark_name() must be overridden")

    def __init__(
        self, children, meta: Optional[Meta] = None, parentheses: bool = False
    ):
        super().__init__(children, meta)
        self._parentheses = parentheses

    def _wrap_into_parentheses(
        self,
        value: str,
        _options=SerializationOptions(),
        context=SerializationContext(),
    ) -> str:
        """Wrap value in parentheses if inside a nested expression."""
        # do not wrap into parentheses if
        #   1. already wrapped or
        #   2. is top-level expression (unless explicitly wrapped)
        if context.inside_parentheses:
            return value
        # Look through ExprTermRule wrapper to determine if truly nested
        parent = getattr(self, "parent", None)
        if parent is None:
            return value
        if isinstance(parent, ExprTermRule):
            if not isinstance(parent.parent, ExpressionRule):
                return value
        elif not isinstance(parent, ExpressionRule):
            return value
        return wrap_into_parentheses(value)


class ExprTermRule(ExpressionRule):
    """Rule for expression terms, optionally wrapped in parentheses."""

    _children_layout: Tuple[
        Optional[LPAR],
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        Optional[RPAR],
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "expr_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        parentheses = False
        if (
            isinstance(children[0], LarkToken)
            and children[0].lark_name() == "LPAR"
            and isinstance(children[-1], LarkToken)
            and children[-1].lark_name() == "RPAR"
        ):
            parentheses = True
        else:
            children = [None, *children, None]
        self._insert_optionals(children, [1, 3])
        super().__init__(children, meta, parentheses)

    @property
    def parentheses(self) -> bool:
        """Return whether this term is wrapped in parentheses."""
        return self._parentheses

    @property
    def expression(self) -> ExpressionRule:
        """Return the inner expression."""
        return self._children[2]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize, handling parenthesized expression wrapping."""
        with context.modify(
            inside_parentheses=self.parentheses or context.inside_parentheses
        ):
            result = self.expression.serialize(options, context)

        if self.parentheses:
            result = wrap_into_parentheses(result)
            if not context.inside_dollar_string:
                result = to_dollar_string(result)

        return result


class ConditionalRule(ExpressionRule):
    """Rule for ternary conditional expressions (condition ? true : false)."""

    _children_layout: Tuple[
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        QMARK,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
        Optional[NewLineOrCommentRule],
        COLON,
        Optional[NewLineOrCommentRule],
        ExpressionRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "conditional"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._insert_optionals(children, [1, 3, 5, 7])
        super().__init__(children, meta)

    @property
    def condition(self) -> ExpressionRule:
        """Return the condition expression."""
        return self._children[0]

    @property
    def if_true(self) -> ExpressionRule:
        """Return the true-branch expression."""
        return self._children[4]

    @property
    def if_false(self) -> ExpressionRule:
        """Return the false-branch expression."""
        return self._children[8]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to ternary expression string."""
        with context.modify(inside_dollar_string=True):
            result = (
                f"{self.condition.serialize(options, context)} "
                f"? {self.if_true.serialize(options, context)} "
                f": {self.if_false.serialize(options, context)}"
            )

        if not context.inside_dollar_string:
            result = to_dollar_string(result)

        if options.force_operation_parentheses:
            result = self._wrap_into_parentheses(result, options, context)

        return result


class BinaryTermRule(ExpressionRule):
    """Rule for the operator+operand portion of a binary operation."""

    _children_layout: Tuple[
        Optional[NewLineOrCommentRule],
        BinaryOperatorRule,
        Optional[NewLineOrCommentRule],
        ExprTermRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "binary_term"

    def __init__(self, children, meta: Optional[Meta] = None):
        self._insert_optionals(children, [0, 2])
        super().__init__(children, meta)

    @property
    def binary_operator(self) -> BinaryOperatorRule:
        """Return the binary operator."""
        return self._children[1]

    @property
    def expr_term(self) -> ExprTermRule:
        """Return the right-hand operand."""
        return self._children[3]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'operator operand' string."""
        op_str = self.binary_operator.serialize(options, context)
        term_str = self.expr_term.serialize(options, context)
        return f"{op_str} {term_str}"


class BinaryOpRule(ExpressionRule):
    """Rule for complete binary operations (lhs operator rhs)."""

    _children_layout: Tuple[
        ExprTermRule,
        BinaryTermRule,
        Optional[NewLineOrCommentRule],
    ]

    def __init__(self, children, meta: Optional[Meta] = None):
        self._insert_optionals(children, [2])
        super().__init__(children, meta)

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "binary_op"

    @property
    def expr_term(self) -> ExprTermRule:
        """Return the left-hand operand."""
        return self._children[0]

    @property
    def binary_term(self) -> BinaryTermRule:
        """Return the binary term (operator + right-hand operand)."""
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'lhs operator rhs' string."""
        with context.modify(inside_dollar_string=True):
            lhs = self.expr_term.serialize(options, context)
            operator = self.binary_term.binary_operator.serialize(options, context)
            rhs = self.binary_term.expr_term.serialize(options, context)

        result = f"{lhs} {operator} {rhs}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)

        if options.force_operation_parentheses:
            result = self._wrap_into_parentheses(result, options, context)
        return result


class UnaryOpRule(ExpressionRule):
    """Rule for unary operations (e.g. negation, logical not)."""

    _children_layout: Tuple[LarkToken, ExprTermRule]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "unary_op"

    @property
    def operator(self) -> str:
        """Return the unary operator string."""
        return str(self._children[0])

    @property
    def expr_term(self):
        """Return the operand."""
        return self._children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to 'operator operand' string."""
        with context.modify(inside_dollar_string=True):
            result = f"{self.operator}{self.expr_term.serialize(options, context)}"

        if not context.inside_dollar_string:
            result = to_dollar_string(result)

        if options.force_operation_parentheses:
            result = self._wrap_into_parentheses(result, options, context)

        return result
