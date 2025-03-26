from abc import ABC
from typing import Tuple, Any, List, Optional

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import TokenSequence, LarkRule, LarkToken


class TokenSequenceRule(LarkRule, ABC):

    _children: Tuple[TokenSequence]

    def __init__(self, children: List[LarkToken], meta: Optional[Meta] = None):
        children = [TokenSequence(children)]
        super().__init__(children)

    def serialize(self) -> Any:
        return self._children[0].joined()


class IdentifierRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "identifier"

    def serialize(self) -> str:
        return str(super().serialize())


class IntLitRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "int_lit"

    def serialize(self) -> float:
        return int(super().serialize())


class FloatLitRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "float_lit"

    def serialize(self) -> float:
        return float(super().serialize())


class StringLitRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "STRING_LIT"

    def serialize(self) -> str:
        return str(super().serialize())


class BinaryOperatorRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "binary_operator"

    def serialize(self) -> str:
        return str(super().serialize())
