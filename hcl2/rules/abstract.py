"""Abstract base classes for the LarkElement tree intermediate representation."""

from abc import ABC, abstractmethod
from typing import Any, Union, List, Optional, Callable

from lark import Token, Tree
from lark.tree import Meta

from hcl2.utils import SerializationOptions, SerializationContext


class LarkElement(ABC):
    """Base class for all elements in the LarkElement tree."""

    @staticmethod
    @abstractmethod
    def lark_name() -> str:
        """Return the corresponding Lark grammar rule or token name."""
        raise NotImplementedError()

    def __init__(self, index: int = -1, parent: Optional["LarkElement"] = None):
        self._index = index
        self._parent = parent

    def set_index(self, i: int):
        """Set the position index of this element within its parent."""
        self._index = i

    def set_parent(self, node: "LarkElement"):
        """Set the parent element that contains this element."""
        self._parent = node

    @abstractmethod
    def to_lark(self) -> Any:
        """Convert this element back to a Lark Tree or Token."""
        raise NotImplementedError()

    @abstractmethod
    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize this element to a Python object (dict, list, str, etc.)."""
        raise NotImplementedError()


class LarkToken(LarkElement, ABC):
    """Base class for terminal token elements (leaves of the tree)."""

    def __init__(self, value: Optional[Union[str, int, float]] = None):
        self._value = value
        super().__init__()

    @property
    @abstractmethod
    def serialize_conversion(self) -> Callable:
        """Return the callable used to convert this token's value during serialization."""
        raise NotImplementedError()

    @property
    def value(self):
        """Return the raw value of this token."""
        return self._value

    def set_value(self, value: Any):
        """Set the raw value of this token."""
        self._value = value

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize this token using its serialize_conversion callable."""
        return self.serialize_conversion(self.value)

    def to_lark(self) -> Token:
        """Convert this token back to a Lark Token."""
        return Token(self.lark_name(), self.value)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"<LarkToken instance: {self.lark_name()} {self.value}>"


class LarkRule(LarkElement, ABC):
    """Base class for non-terminal rule elements (internal nodes of the tree).

    Subclasses should declare `_children_layout: Tuple[...]` (without assignment)
    to document the expected positional structure of `_children`. For variable-length
    rules, use `_children_layout: List[Union[...]]`. This annotation exists only in
    `__annotations__` and does not create an attribute or conflict with the runtime
    `_children` list.
    """

    @abstractmethod
    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        """Serialize this rule and its children to a Python object."""
        raise NotImplementedError()

    @property
    def children(self) -> List[Any]:
        """Return the list of child elements."""
        return self._children

    @property
    def parent(self):
        """Return the parent element."""
        return self._parent

    @property
    def index(self):
        """Return the position index within the parent."""
        return self._index

    def to_lark(self) -> Tree:
        """Convert this rule and its children back to a Lark Tree."""
        result_children = []
        for child in self._children:
            if child is None:
                continue

            result_children.append(child.to_lark())

        return Tree(self.lark_name(), result_children, meta=self._meta)

    def __init__(self, children: List[Any], meta: Optional[Meta] = None):
        super().__init__()
        self._children: List[Any] = children
        self._meta = meta or Meta()

        for index, child in enumerate(children):
            if child is not None:
                child.set_index(index)
                child.set_parent(self)

    def __repr__(self):
        return f"<LarkRule: {self.__class__.__name__}>"
