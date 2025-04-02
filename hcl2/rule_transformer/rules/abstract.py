from abc import ABC, abstractmethod
from typing import Any, Union, List, Optional

from lark import Token, Tree
from lark.tree import Meta

from hcl2.rule_transformer.utils import SerializationOptions


class LarkElement(ABC):
    @abstractmethod
    def reverse(self) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        raise NotImplementedError()


class LarkToken(LarkElement):
    def __init__(self, name: str, value: Union[str, int]):
        self._name = name
        self._value = value

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self):
        return self._value

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return self._value

    def reverse(self) -> Token:
        return Token(self.name, self.value)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"<LarkToken instance: {self._name} {self._value}>"


EQ_Token = LarkToken
COLON_TOKEN = LarkToken
LPAR_TOKEN = LarkToken  # left parenthesis
RPAR_TOKEN = LarkToken  # right parenthesis


class TokenSequence(LarkElement):
    def __init__(self, tokens: List[LarkToken]):
        self.tokens = tokens

    def reverse(self) -> List[Token]:
        return [token.reverse() for token in self.tokens]

    def serialize(self, options: SerializationOptions = SerializationOptions()):
        return "".join(str(token) for token in self.tokens)


class LarkRule(LarkElement, ABC):
    @staticmethod
    @abstractmethod
    def rule_name() -> str:
        raise NotImplementedError()

    @abstractmethod
    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        raise NotImplementedError()

    @property
    def children(self) -> List[LarkElement]:
        return self._children

    def reverse(self) -> Tree:
        result_children = []
        for child in self._children:
            if child is None:
                continue

            if isinstance(child, TokenSequence):
                result_children.extend(child.reverse())
            else:
                result_children.append(child.reverse())

        return Tree(self.rule_name(), result_children, meta=self._meta)

    def __init__(self, children: List, meta: Optional[Meta] = None):
        self._children = children
        self._meta = meta

    def __repr__(self):
        return f"<LarkRule: {self.__class__.__name__} ({';'.join(str(child) for child in self._children)})>"
