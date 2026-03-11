"""Rule classes for HCL2 template directives (%{if}, %{for})."""

from typing import Any, List, Optional, Tuple

from lark.tree import Meta

from hcl2.rules.abstract import LarkRule
from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import (
    DIRECTIVE_START,
    STRIP_MARKER,
    IF,
    ELSE,
    ENDIF,
    FOR,
    IN,
    ENDFOR,
    COMMA,
    RBRACE,
    StaticStringToken,
)
from hcl2.utils import SerializationOptions, SerializationContext


def _is_strip(child) -> bool:
    """Check if a child is a STRIP_MARKER token."""
    return isinstance(child, StaticStringToken) and child.lark_name() == "STRIP_MARKER"


def _strip_prefix(is_strip: bool) -> str:
    """Return strip-marker prefix string for directive serialization."""
    return "~ " if is_strip else " "


def _strip_suffix(is_strip: bool) -> str:
    """Return strip-marker suffix string for directive serialization."""
    return " ~" if is_strip else " "


def _insert_strip_optionals(children: List, indexes: List[int]):
    """Insert None placeholders at positions where optional STRIP_MARKER may appear."""
    for index in sorted(indexes):
        try:
            child = children[index]
        except IndexError:
            children.insert(index, None)
        else:
            if not _is_strip(child):
                children.insert(index, None)


class TemplateIfStartRule(LarkRule):
    """Rule for %{if condition} opening directive."""

    _children_layout: Tuple[
        DIRECTIVE_START,
        Optional[STRIP_MARKER],
        IF,
        ExpressionRule,
        Optional[STRIP_MARKER],
        RBRACE,
    ]

    def __init__(self, children, meta: Optional[Meta] = None):
        _insert_strip_optionals(children, [1, 4])
        super().__init__(children, meta)

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_if_start"

    @property
    def strip_open(self) -> bool:
        """Check if there's a strip marker after %{."""
        return self._children[1] is not None

    @property
    def condition(self) -> ExpressionRule:
        """Return the condition expression."""
        return self._children[3]

    @property
    def strip_close(self) -> bool:
        """Check if there's a strip marker before }."""
        return self._children[4] is not None

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to %{ if EXPR } or %{~ if EXPR ~}."""
        with context.modify(inside_dollar_string=True):
            cond_str = self.condition.serialize(options, context)
        prefix = _strip_prefix(self.strip_open)
        suffix = _strip_suffix(self.strip_close)
        return f"%{{{prefix}if {cond_str}{suffix}}}"


class TemplateElseRule(LarkRule):
    """Rule for %{else} directive."""

    _children_layout: Tuple[
        DIRECTIVE_START,
        Optional[STRIP_MARKER],
        ELSE,
        Optional[STRIP_MARKER],
        RBRACE,
    ]

    def __init__(self, children, meta: Optional[Meta] = None):
        _insert_strip_optionals(children, [1, 3])
        super().__init__(children, meta)

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_else"

    @property
    def strip_open(self) -> bool:
        """Check if there's a strip marker after %{."""
        return self._children[1] is not None

    @property
    def strip_close(self) -> bool:
        """Check if there's a strip marker before }."""
        return self._children[3] is not None

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to %{ else } or %{~ else ~}."""
        prefix = _strip_prefix(self.strip_open)
        suffix = _strip_suffix(self.strip_close)
        return f"%{{{prefix}else{suffix}}}"


class TemplateEndifRule(LarkRule):
    """Rule for %{endif} directive."""

    _children_layout: Tuple[
        DIRECTIVE_START,
        Optional[STRIP_MARKER],
        ENDIF,
        Optional[STRIP_MARKER],
        RBRACE,
    ]

    def __init__(self, children, meta: Optional[Meta] = None):
        _insert_strip_optionals(children, [1, 3])
        super().__init__(children, meta)

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_endif"

    @property
    def strip_open(self) -> bool:
        """Check if there's a strip marker after %{."""
        return self._children[1] is not None

    @property
    def strip_close(self) -> bool:
        """Check if there's a strip marker before }."""
        return self._children[3] is not None

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to %{ endif } or %{~ endif ~}."""
        prefix = _strip_prefix(self.strip_open)
        suffix = _strip_suffix(self.strip_close)
        return f"%{{{prefix}endif{suffix}}}"


class TemplateForStartRule(LarkRule):
    """Rule for %{for VAR in EXPR} opening directive."""

    _children_layout: Tuple[
        DIRECTIVE_START,
        Optional[STRIP_MARKER],
        FOR,
        IdentifierRule,
        Optional[COMMA],
        Optional[IdentifierRule],
        IN,
        ExpressionRule,
        Optional[STRIP_MARKER],
        RBRACE,
    ]

    def __init__(self, children, meta: Optional[Meta] = None):
        self._setup_optionals(children)
        super().__init__(children, meta)

    def _setup_optionals(self, children: List):
        """Insert None placeholders for optional strip markers and second iterator.

        Parser output varies:
          [DIRECTIVE_START, STRIP?, FOR, id, (COMMA, id)?, IN, expr, STRIP?, RBRACE]
        Target layout (10 positions):
          [0:DIRECTIVE_START, 1:STRIP?, 2:FOR, 3:id, 4:COMMA?, 5:id?, 6:IN, 7:expr, 8:STRIP?, 9:RBRACE]
        """
        # Step 1: Insert strip_open placeholder at position 1
        _insert_strip_optionals(children, [1])

        # Step 2: Handle optional comma + second identifier
        # After step 1, FOR is at index 2, first identifier at 3.
        # Count identifiers before IN to distinguish iterator(s) from collection
        ids_before_in = []
        for child in children:
            if isinstance(child, StaticStringToken) and child.lark_name() == "IN":
                break
            if isinstance(child, IdentifierRule):
                ids_before_in.append(child)
        if len(ids_before_in) < 2:
            # No second iterator — insert None for COMMA and second id at 4, 5
            children.insert(4, None)
            children.insert(5, None)

        # Step 3: Insert strip_close placeholder at position 8
        _insert_strip_optionals(children, [8])

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_for_start"

    @property
    def strip_open(self) -> bool:
        """Check if there's a strip marker after %{."""
        return self._children[1] is not None

    @property
    def strip_close(self) -> bool:
        """Check if there's a strip marker before }."""
        return self._children[8] is not None

    @property
    def iterator(self) -> IdentifierRule:
        """Return the first iterator identifier."""
        return self._children[3]

    @property
    def key_iterator(self) -> Optional[IdentifierRule]:
        """Return the second iterator identifier, or None."""
        return self._children[5]

    @property
    def collection(self) -> ExpressionRule:
        """Return the collection expression after IN."""
        return self._children[7]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to %{ for VAR in EXPR } or %{~ for VAR in EXPR ~}."""
        prefix = _strip_prefix(self.strip_open)
        suffix = _strip_suffix(self.strip_close)
        with context.modify(inside_dollar_string=True):
            iter_str = self.iterator.serialize(options, context)
            if self.key_iterator is not None:
                iter_str += f", {self.key_iterator.serialize(options, context)}"
            coll_str = self.collection.serialize(options, context)
        return f"%{{{prefix}for {iter_str} in {coll_str}{suffix}}}"


class TemplateEndforRule(LarkRule):
    """Rule for %{endfor} directive."""

    _children_layout: Tuple[
        DIRECTIVE_START,
        Optional[STRIP_MARKER],
        ENDFOR,
        Optional[STRIP_MARKER],
        RBRACE,
    ]

    def __init__(self, children, meta: Optional[Meta] = None):
        _insert_strip_optionals(children, [1, 3])
        super().__init__(children, meta)

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_endfor"

    @property
    def strip_open(self) -> bool:
        """Check if there's a strip marker after %{."""
        return self._children[1] is not None

    @property
    def strip_close(self) -> bool:
        """Check if there's a strip marker before }."""
        return self._children[3] is not None

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize to %{ endfor } or %{~ endfor ~}."""
        prefix = _strip_prefix(self.strip_open)
        suffix = _strip_suffix(self.strip_close)
        return f"%{{{prefix}endfor{suffix}}}"


class TemplateIfRule(LarkRule):
    """Assembled rule for a complete %{if}...%{else}...%{endif} template.

    This is NOT produced by the parser directly — it is assembled by the
    transformer from flat TemplateIfStartRule/TemplateElseRule/TemplateEndifRule
    and interleaved StringPartRule children.
    """

    _children_layout: Tuple[
        TemplateIfStartRule,
        # ... variable number of body StringPartRules ...
        # Optional[TemplateElseRule],
        # ... variable number of else body StringPartRules ...
        TemplateEndifRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_if"

    def __init__(  # pylint: disable=R0917
        self,
        if_start: TemplateIfStartRule,
        if_body: list,
        else_rule: Optional[TemplateElseRule],
        else_body: Optional[list],
        endif: TemplateEndifRule,
        meta: Optional[Meta] = None,
    ):
        self._if_start = if_start
        self._if_body = if_body
        self._else_rule = else_rule
        self._else_body = else_body or []
        self._endif = endif

        # Build children list for to_lark
        children = [if_start, *if_body]
        if else_rule is not None:
            children.extend([else_rule, *self._else_body])
        children.append(endif)
        super().__init__(children, meta)

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize the full if/else/endif directive."""
        result = self._if_start.serialize(options, context)
        for part in self._if_body:
            result += part.serialize(options, context)
        if self._else_rule is not None:
            result += self._else_rule.serialize(options, context)
            for part in self._else_body:
                result += part.serialize(options, context)
        result += self._endif.serialize(options, context)
        return result

    def to_lark(self):
        """Convert back to flat sequence of Lark trees for reconstruction."""
        result_children = []
        result_children.extend(self._if_start.to_lark().children)
        for part in self._if_body:
            result_children.append(part.to_lark())
        if self._else_rule is not None:
            result_children.extend(self._else_rule.to_lark().children)
            for part in self._else_body:
                result_children.append(part.to_lark())
        result_children.extend(self._endif.to_lark().children)
        from lark import Tree  # pylint: disable=C0415

        return Tree("template_if", result_children, meta=self._meta)


class TemplateForRule(LarkRule):
    """Assembled rule for a complete %{for}...%{endfor} template."""

    _children_layout: Tuple[
        TemplateForStartRule,
        # ... variable number of body StringPartRules ...
        TemplateEndforRule,
    ]

    @staticmethod
    def lark_name() -> str:
        """Return the grammar rule name."""
        return "template_for"

    def __init__(
        self,
        for_start: TemplateForStartRule,
        body: list,
        endfor: TemplateEndforRule,
        meta: Optional[Meta] = None,
    ):
        self._for_start = for_start
        self._body = body
        self._endfor = endfor

        children = [for_start, *body, endfor]
        super().__init__(children, meta)

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize the full for/endfor directive."""
        result = self._for_start.serialize(options, context)
        for part in self._body:
            result += part.serialize(options, context)
        result += self._endfor.serialize(options, context)
        return result

    def to_lark(self):
        """Convert back to flat sequence of Lark trees for reconstruction."""
        result_children = []
        result_children.extend(self._for_start.to_lark().children)
        for part in self._body:
            result_children.append(part.to_lark())
        result_children.extend(self._endfor.to_lark().children)
        from lark import Tree  # pylint: disable=C0415

        return Tree("template_for", result_children, meta=self._meta)
