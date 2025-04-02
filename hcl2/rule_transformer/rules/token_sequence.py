from abc import ABC
from typing import Tuple, Any, List, Optional, Type

from lark.tree import Meta

from hcl2.rule_transformer.rules.abstract import TokenSequence, LarkRule, LarkToken
from hcl2.rule_transformer.utils import SerializationOptions


class TokenSequenceRule(LarkRule, ABC):

    _children: Tuple[TokenSequence]

    def __init__(self, children: List[LarkToken], meta: Optional[Meta] = None):
        children = [TokenSequence(children)]
        super().__init__(children, meta)

    def serialized_type(self) -> Type:
        return str

    def serialize(self, options: SerializationOptions = SerializationOptions()) -> Any:
        return self.serialized_type()(self._children[0].serialize(options))


class IdentifierRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "identifier"


class IntLitRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "int_lit"

    def serialized_type(self) -> Type:
        return int


class FloatLitRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "float_lit"

    def serialized_type(self) -> Type:
        return float


class StringLitRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        # TODO actually this is a terminal, but it doesn't matter for lark.Transformer class;
        #   nevertheless, try to change it to a rule in hcl2.lark
        return "STRING_LIT"


class BinaryOperatorRule(TokenSequenceRule):
    @staticmethod
    def rule_name() -> str:
        return "binary_operator"
