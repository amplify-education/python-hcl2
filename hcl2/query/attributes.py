"""AttributeView facade."""

from typing import Any

from hcl2.query._base import NodeView, register_view, view_for
from hcl2.rules.base import AttributeRule


@register_view(AttributeRule)
class AttributeView(NodeView):
    """View over an HCL2 attribute (AttributeRule)."""

    @property
    def name(self) -> str:
        """Return the attribute name as a plain string."""
        node: AttributeRule = self._node  # type: ignore[assignment]
        return node.identifier.serialize()

    @property
    def value(self) -> Any:
        """Return the serialized Python value of the attribute expression."""
        node: AttributeRule = self._node  # type: ignore[assignment]
        return node.expression.serialize()

    @property
    def value_node(self) -> "NodeView":
        """Return a view over the expression node."""
        node: AttributeRule = self._node  # type: ignore[assignment]
        return view_for(node.expression)
