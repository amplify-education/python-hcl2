"""View facade for HCL2 conditional expressions."""

from hcl2.query._base import NodeView, register_view, view_for
from hcl2.rules.expressions import ConditionalRule


@register_view(ConditionalRule)
class ConditionalView(NodeView):
    """View over a ternary conditional expression (condition ? true : false)."""

    @property
    def condition(self) -> NodeView:
        """Return the condition expression."""
        node: ConditionalRule = self._node  # type: ignore[assignment]
        return view_for(node.condition)

    @property
    def true_val(self) -> NodeView:
        """Return the true-branch expression."""
        node: ConditionalRule = self._node  # type: ignore[assignment]
        return view_for(node.if_true)

    @property
    def false_val(self) -> NodeView:
        """Return the false-branch expression."""
        node: ConditionalRule = self._node  # type: ignore[assignment]
        return view_for(node.if_false)
