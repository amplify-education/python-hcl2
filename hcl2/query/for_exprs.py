"""ForTupleView and ForObjectView facades."""

from typing import Optional

from hcl2.query._base import NodeView, register_view, view_for
from hcl2.rules.for_expressions import ForObjectExprRule, ForTupleExprRule


@register_view(ForTupleExprRule)
class ForTupleView(NodeView):
    """View over a for-tuple expression ([for ...])."""

    @property
    def iterator_name(self) -> str:
        """Return the first iterator identifier name."""
        node: ForTupleExprRule = self._node  # type: ignore[assignment]
        return node.for_intro.first_iterator.serialize()

    @property
    def second_iterator_name(self) -> Optional[str]:
        """Return the second iterator identifier name, or None."""
        node: ForTupleExprRule = self._node  # type: ignore[assignment]
        second = node.for_intro.second_iterator
        if second is None:
            return None
        return second.serialize()

    @property
    def iterable(self) -> NodeView:
        """Return a view over the iterable expression."""
        node: ForTupleExprRule = self._node  # type: ignore[assignment]
        return view_for(node.for_intro.iterable)

    @property
    def value_expr(self) -> NodeView:
        """Return a view over the value expression."""
        node: ForTupleExprRule = self._node  # type: ignore[assignment]
        return view_for(node.value_expr)

    @property
    def has_condition(self) -> bool:
        """Return whether the for expression has an if condition."""
        node: ForTupleExprRule = self._node  # type: ignore[assignment]
        return node.condition is not None

    @property
    def condition(self) -> Optional[NodeView]:
        """Return a view over the condition, or None."""
        node: ForTupleExprRule = self._node  # type: ignore[assignment]
        cond = node.condition
        if cond is None:
            return None
        return view_for(cond)


@register_view(ForObjectExprRule)
class ForObjectView(NodeView):
    """View over a for-object expression ({for ...})."""

    @property
    def iterator_name(self) -> str:
        """Return the first iterator identifier name."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        return node.for_intro.first_iterator.serialize()

    @property
    def second_iterator_name(self) -> Optional[str]:
        """Return the second iterator identifier name, or None."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        second = node.for_intro.second_iterator
        if second is None:
            return None
        return second.serialize()

    @property
    def iterable(self) -> NodeView:
        """Return a view over the iterable expression."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        return view_for(node.for_intro.iterable)

    @property
    def key_expr(self) -> NodeView:
        """Return a view over the key expression."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        return view_for(node.key_expr)

    @property
    def value_expr(self) -> NodeView:
        """Return a view over the value expression."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        return view_for(node.value_expr)

    @property
    def has_ellipsis(self) -> bool:
        """Return whether the for expression has an ellipsis."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        return node.ellipsis is not None

    @property
    def has_condition(self) -> bool:
        """Return whether the for expression has an if condition."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        return node.condition is not None

    @property
    def condition(self) -> Optional[NodeView]:
        """Return a view over the condition, or None."""
        node: ForObjectExprRule = self._node  # type: ignore[assignment]
        cond = node.condition
        if cond is None:
            return None
        return view_for(cond)
