from abc import ABC, abstractmethod
from typing import List, Optional, Any, Union


class LarkNode(ABC):
    """Base class for all nodes in the tree"""

    def __init__(self, index: int = -1, parent: Optional["Node"] = None):
        self._index = index
        self._parent = parent

    @property
    def parent(self) -> Optional["Node"]:
        return self._parent

    @property
    def index(self) -> int:
        return self._index

    def set_parent(self, parent: "Node"):
        self._parent = parent

    def set_index(self, index: int):
        self._index = index

    @abstractmethod
    def serialize(self, options=None) -> Any:
        pass

    @abstractmethod
    def to_lark(self) -> Any:
        """Convert back to Lark representation"""
        pass

    def is_leaf(self) -> bool:
        """Check if this is a leaf node (atomic token)"""
        return isinstance(self, LeafNode)

    def is_sequence(self) -> bool:
        """Check if this is a token sequence node"""
        return isinstance(self, SequenceNode)

    def is_internal(self) -> bool:
        """Check if this is an internal node (grammar rule)"""
        return isinstance(self, InternalNode)

    def is_atomic(self) -> bool:
        """Check if this represents an atomic value (leaf or sequence)"""
        return self.is_leaf() or self.is_sequence()


class LarkLeaf(Node, ABC):
    """"""

    def __init__(self, value: Any, index: int = -1, parent: Optional[TreeNode] = None):
        super().__init__(index, parent)
        self._value = value

    @property
    def value(self) -> Any:
        return self._value

    def serialize(self, options=None) -> Any:
        return self._value


class InternalNode(Node):
    def __init__(
        self, children: List[Node], index: int = -1, parent: Optional[Node] = None
    ):
        super().__init__(index, parent)
        self._children = children or []

        # Set parent and index for all children
        for i, child in enumerate(self._children):
            if child is not None:
                child.set_parent(self)
                child.set_index(i)

    @property
    def children(self) -> List[Node]:
        return self._children

    def add_child(self, child: Node):
        """Add a child to this internal node"""
        child.set_parent(self)
        child.set_index(len(self._children))
        self._children.append(child)

    def remove_child(self, index: int) -> Optional[Node]:
        """Remove child at given index"""
        if 0 <= index < len(self._children):
            child = self._children.pop(index)
            if child:
                child.set_parent(None)
            # Update indices for remaining children
            for i in range(index, len(self._children)):
                if self._children[i]:
                    self._children[i].set_index(i)
            return child
        return None

    @abstractmethod
    def rule_name(self) -> str:
        """The name of the grammar rule this represents"""
        pass
