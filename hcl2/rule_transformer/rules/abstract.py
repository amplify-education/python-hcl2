from abc import ABC, abstractmethod
from typing import Any, Union, List, Optional, Tuple, Callable

from lark import Token, Tree
from lark.exceptions import VisitError
from lark.tree import Meta

from hcl2.rule_transformer.utils import SerializationOptions, SerializationContext


class LarkElement(ABC):
    @staticmethod
    @abstractmethod
    def lark_name() -> str:
        raise NotImplementedError()

    def __init__(self, index: int = -1, parent: "LarkElement" = None):
        self._index = index
        self._parent = parent

    def set_index(self, i: int):
        self._index = i

    def set_parent(self, node: "LarkElement"):
        self._parent = node

    @abstractmethod
    def to_lark(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        raise NotImplementedError()


class LarkToken(LarkElement, ABC):
    def __init__(self, value: Union[str, int, float]):
        self._value = value
        super().__init__()

    @property
    @abstractmethod
    def serialize_conversion(self) -> Callable:
        raise NotImplementedError()

    @property
    def value(self):
        return self._value

    def set_value(self, value: Any):
        self._value = value

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return self.serialize_conversion(self.value)

    def to_lark(self) -> Token:
        return Token(self.lark_name(), self.value)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"<LarkToken instance: {self.lark_name()} {self.value}>"


class LarkRule(LarkElement, ABC):
    @abstractmethod
    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        raise NotImplementedError()

    @property
    def children(self) -> List[LarkElement]:
        return self._children

    @property
    def parent(self):
        return self._parent

    @property
    def index(self):
        return self._index

    def to_lark(self) -> Tree:
        result_children = []
        for child in self._children:
            if child is None:
                continue

            result_children.append(child.to_lark())

        return Tree(self.lark_name(), result_children, meta=self._meta)

    def __init__(self, children: List[LarkElement], meta: Optional[Meta] = None):
        super().__init__()
        self._children = children
        self._meta = meta or Meta()

        for index, child in enumerate(children):
            if child is not None:
                child.set_index(index)
                child.set_parent(self)

    def __repr__(self):
        return f"<LarkRule: {self.__class__.__name__}>"
