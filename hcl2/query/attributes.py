"""AttributeView facade."""

from typing import Any, List, Optional

from hcl2.query._base import NodeView, register_view, view_for
from hcl2.rules.abstract import LarkElement
from hcl2.rules.base import AttributeRule
from hcl2.utils import SerializationOptions


@register_view(AttributeRule)
class AttributeView(NodeView):
    """View over an HCL2 attribute (AttributeRule)."""

    def __init__(
        self,
        node: LarkElement,
        adjacent_comments: Optional[List[dict]] = None,
    ):
        super().__init__(node)
        self._adjacent_comments = adjacent_comments

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

    def to_dict(self, options: Optional[SerializationOptions] = None) -> Any:
        """Serialize, merging adjacent comments from the parent body."""
        result = super().to_dict(options=options)
        if (
            self._adjacent_comments
            and options is not None
            and options.with_comments
            and isinstance(result, dict)
        ):
            result["__comments__"] = self._adjacent_comments
        return result
