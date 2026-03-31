"""TupleView and ObjectView facades."""

from typing import List, Optional, Tuple

from hcl2.query._base import NodeView, register_view, view_for
from hcl2.rules.containers import ObjectRule, TupleRule


@register_view(TupleRule)
class TupleView(NodeView):
    """View over an HCL2 tuple (TupleRule)."""

    @property
    def elements(self) -> List[NodeView]:
        """Return the tuple elements as views."""
        node: TupleRule = self._node  # type: ignore[assignment]
        return [view_for(elem) for elem in node.elements]

    def __len__(self) -> int:
        node: TupleRule = self._node  # type: ignore[assignment]
        return len(node.elements)

    def __getitem__(self, index: int) -> NodeView:
        node: TupleRule = self._node  # type: ignore[assignment]
        return view_for(node.elements[index])


@register_view(ObjectRule)
class ObjectView(NodeView):
    """View over an HCL2 object (ObjectRule)."""

    @property
    def entries(self) -> List[Tuple[str, NodeView]]:
        """Return (key, value_view) pairs."""
        node: ObjectRule = self._node  # type: ignore[assignment]
        result = []
        for elem in node.elements:
            key = str(elem.key.serialize())
            val = view_for(elem.expression)
            result.append((key, val))
        return result

    def get(self, key: str) -> Optional[NodeView]:
        """Get a value view by key, or None."""
        for entry_key, entry_val in self.entries:
            if entry_key == key:
                return entry_val
        return None

    @property
    def keys(self) -> List[str]:
        """Return all keys as strings."""
        return [k for k, _ in self.entries]
