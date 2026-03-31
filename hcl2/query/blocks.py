"""BlockView facade."""

from typing import List, Optional

from hcl2.query._base import NodeView, register_view
from hcl2.rules.base import BlockRule
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.strings import StringRule


def _label_to_str(label) -> str:
    """Convert a block label (IdentifierRule or StringRule) to a plain string."""
    if isinstance(label, IdentifierRule):
        return label.serialize()
    if isinstance(label, StringRule):
        raw = label.serialize()
        # Strip surrounding quotes
        if isinstance(raw, str) and len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            return raw[1:-1]
        return str(raw)
    return str(label.serialize())


@register_view(BlockRule)
class BlockView(NodeView):
    """View over an HCL2 block (BlockRule)."""

    @property
    def block_type(self) -> str:
        """Return the block type (first label) as a plain string."""
        node: BlockRule = self._node  # type: ignore[assignment]
        return _label_to_str(node.labels[0])

    @property
    def labels(self) -> List[str]:
        """Return all labels as plain strings."""
        node: BlockRule = self._node  # type: ignore[assignment]
        return [_label_to_str(lbl) for lbl in node.labels]

    @property
    def name_labels(self) -> List[str]:
        """Return labels after the block type (labels[1:]) as plain strings."""
        return self.labels[1:]

    @property
    def body(self) -> "NodeView":
        """Return the block body as a BodyView."""
        from hcl2.query.body import BodyView

        node: BlockRule = self._node  # type: ignore[assignment]
        return BodyView(node.body)

    def blocks(
        self, block_type: Optional[str] = None, *labels: str
    ) -> List["NodeView"]:
        """Delegate to body."""
        from hcl2.query.body import BodyView

        node: BlockRule = self._node  # type: ignore[assignment]
        return BodyView(node.body).blocks(block_type, *labels)

    def attributes(self, name: Optional[str] = None) -> List["NodeView"]:
        """Delegate to body."""
        from hcl2.query.body import BodyView

        node: BlockRule = self._node  # type: ignore[assignment]
        return BodyView(node.body).attributes(name)

    def attribute(self, name: str) -> Optional["NodeView"]:
        """Delegate to body."""
        from hcl2.query.body import BodyView

        node: BlockRule = self._node  # type: ignore[assignment]
        return BodyView(node.body).attribute(name)
