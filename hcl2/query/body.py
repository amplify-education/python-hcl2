"""DocumentView and BodyView facades."""

from typing import List, Optional

from hcl2.query._base import NodeView, register_view
from hcl2.rules.base import AttributeRule, BlockRule, BodyRule, StartRule
from hcl2.rules.whitespace import NewLineOrCommentRule


def _collect_leading_comments(body: BodyRule, child_index: int) -> List[dict]:
    """Collect comments from NewLineOrCommentRule siblings preceding *child_index*.

    Walks backward through ``body.children`` from ``child_index - 1``,
    collecting comment dicts via ``to_list()``, stopping at the first
    ``BlockRule`` or ``AttributeRule`` (the previous semantic sibling) or
    the start of the children list.
    """
    chunks: List[List[dict]] = []
    for i in range(child_index - 1, -1, -1):
        sibling = body.children[i]
        if isinstance(sibling, (BlockRule, AttributeRule)):
            break
        if isinstance(sibling, NewLineOrCommentRule):
            comments = sibling.to_list()
            if comments:
                chunks.append(comments)
    # Reverse node order (walked backward) but keep each node's comments in order
    chunks.reverse()
    result: List[dict] = []
    for chunk in chunks:
        result.extend(chunk)
    return result


@register_view(StartRule)
class DocumentView(NodeView):
    """View over the top-level HCL2 document (StartRule)."""

    @staticmethod
    def parse(text: str) -> "DocumentView":
        """Parse HCL2 text into a DocumentView."""
        from hcl2 import api

        tree = api.parses(text)
        return DocumentView(tree)

    @staticmethod
    def parse_file(path: str) -> "DocumentView":
        """Parse an HCL2 file into a DocumentView."""
        from hcl2 import api

        with open(path, encoding="utf-8") as f:
            tree = api.parse(f)
        return DocumentView(tree)

    @property
    def body(self) -> "BodyView":
        """Return the document body as a BodyView."""
        node: StartRule = self._node  # type: ignore[assignment]
        return BodyView(node.body)

    def blocks(
        self, block_type: Optional[str] = None, *labels: str
    ) -> List["NodeView"]:
        """Return matching blocks, delegating to body."""
        return self.body.blocks(block_type, *labels)

    def attributes(self, name: Optional[str] = None) -> List["NodeView"]:
        """Return matching attributes, delegating to body."""
        return self.body.attributes(name)

    def attribute(self, name: str) -> Optional["NodeView"]:
        """Return a single attribute by name, or None."""
        return self.body.attribute(name)


@register_view(BodyRule)
class BodyView(NodeView):
    """View over an HCL2 body (BodyRule)."""

    def blocks(
        self, block_type: Optional[str] = None, *labels: str
    ) -> List["NodeView"]:
        """Return blocks, optionally filtered by type and labels."""
        from hcl2.query.blocks import BlockView

        node: BodyRule = self._node  # type: ignore[assignment]
        results: List[NodeView] = []
        for child in node.children:
            if not isinstance(child, BlockRule):
                continue
            adjacent = _collect_leading_comments(node, child.index) or None
            block_view = BlockView(child, adjacent_comments=adjacent)
            if block_type is not None and block_view.block_type != block_type:
                continue
            if labels:
                name_lbls = block_view.name_labels
                if len(labels) > len(name_lbls):
                    continue
                if any(l != nl for l, nl in zip(labels, name_lbls)):
                    continue
            results.append(block_view)
        return results

    def attributes(self, name: Optional[str] = None) -> List["NodeView"]:
        """Return attributes, optionally filtered by name."""
        from hcl2.query.attributes import AttributeView

        node: BodyRule = self._node  # type: ignore[assignment]
        results: List[NodeView] = []
        for child in node.children:
            if not isinstance(child, AttributeRule):
                continue
            adjacent = _collect_leading_comments(node, child.index) or None
            attr_view = AttributeView(child, adjacent_comments=adjacent)
            if name is not None and attr_view.name != name:
                continue
            results.append(attr_view)
        return results

    def attribute(self, name: str) -> Optional["NodeView"]:
        """Return a single attribute by name, or None."""
        attrs = self.attributes(name)
        return attrs[0] if attrs else None
