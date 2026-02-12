import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, TextIO, List, Union, Optional

from regex import regex

from hcl2 import parses
from hcl2.const import IS_BLOCK
from hcl2.rule_transformer.rules.abstract import LarkElement, LarkRule
from hcl2.rule_transformer.rules.base import (
    BlockRule,
    AttributeRule,
    BodyRule,
    StartRule,
)
from hcl2.rule_transformer.rules.containers import (
    TupleRule,
    ObjectRule,
    ObjectElemRule,
    ObjectElemKeyExpressionRule,
    ObjectElemKeyDotAccessor,
    ObjectElemKeyRule,
)
from hcl2.rule_transformer.rules.expressions import ExprTermRule
from hcl2.rule_transformer.rules.literal_rules import (
    IdentifierRule,
    IntLitRule,
    FloatLitRule,
)
from hcl2.rule_transformer.rules.strings import (
    StringRule,
    InterpolationRule,
    StringPartRule,
    HeredocTemplateRule,
    HeredocTrimTemplateRule,
)
from hcl2.rule_transformer.rules.tokens import (
    NAME,
    EQ,
    DBLQUOTE,
    STRING_CHARS,
    ESCAPED_INTERPOLATION,
    INTERP_START,
    RBRACE,
    IntLiteral,
    FloatLiteral,
    RSQB,
    LSQB,
    COMMA,
    DOT,
    LBRACE,
    HEREDOC_TRIM_TEMPLATE,
    HEREDOC_TEMPLATE,
    COLON,
)
from hcl2.rule_transformer.rules.whitespace import NewLineOrCommentRule
from hcl2.rule_transformer.transformer import RuleTransformer
from hcl2.rule_transformer.utils import HEREDOC_TRIM_PATTERN, HEREDOC_PATTERN


@dataclass
class DeserializerOptions:
    heredocs_to_strings: bool = False
    indent_length: int = 2
    object_elements_colon: bool = False
    object_elements_trailing_comma: bool = True


class LarkElementTreeDeserializer(ABC):
    def __init__(self, options: DeserializerOptions = None):
        self.options = options or DeserializerOptions()

    @abstractmethod
    def loads(self, value: str) -> LarkElement:
        raise NotImplementedError()

    def load(self, file: TextIO) -> LarkElement:
        return self.loads(file.read())


class BaseDeserializer(LarkElementTreeDeserializer):
    def __init__(self, options=None):
        super().__init__(options)
        self._current_line = 1
        self._last_new_line: Optional[NewLineOrCommentRule] = None

    @property
    @lru_cache
    def _transformer(self) -> RuleTransformer:
        return RuleTransformer()

    def load_python(self, value: Any) -> LarkElement:
        result = StartRule([self._deserialize(value)])
        return result

    def loads(self, value: str) -> LarkElement:
        return self.load_python(json.loads(value))

    def _deserialize(self, value: Any) -> LarkElement:
        if isinstance(value, dict):
            if self._contains_block_marker(value):

                children = []

                block_elements = self._deserialize_block_elements(value)
                for element in block_elements:
                    children.append(element)

                return BodyRule(children)

            return self._deserialize_object(value)

        if isinstance(value, list):
            return self._deserialize_list(value)

        return self._deserialize_text(value)

    def _deserialize_block_elements(self, value: dict) -> List[LarkRule]:
        children = []
        for key, value in value.items():
            if self._is_block(value):
                # this value is a list of blocks, iterate over each block and deserialize them
                for block in value:
                    children.append(self._deserialize_block(key, block))

            else:
                # otherwise it's just an attribute
                if key != IS_BLOCK:
                    children.append(self._deserialize_attribute(key, value))

        return children

    def _deserialize_text(self, value: Any) -> LarkRule:
        try:
            int_val = int(value)
            if "." in str(value):
                return FloatLitRule([FloatLiteral(float(value))])
            return IntLitRule([IntLiteral(int_val)])
        except ValueError:
            pass

        if isinstance(value, str):
            if value.startswith('"') and value.endswith('"'):
                if not self.options.heredocs_to_strings and value.startswith('"<<-'):
                    match = HEREDOC_TRIM_PATTERN.match(value[1:-1])
                    if match:
                        return self._deserialize_heredoc(value[1:-1], True)

                if not self.options.heredocs_to_strings and value.startswith('"<<'):
                    match = HEREDOC_PATTERN.match(value[1:-1])
                    if match:
                        return self._deserialize_heredoc(value[1:-1], False)

                return self._deserialize_string(value)

            if self._is_expression(value):
                return self._deserialize_expression(value)

            return self._deserialize_identifier(value)

        elif isinstance(value, bool):
            return self._deserialize_identifier(str(value).lower())

        return self._deserialize_identifier(str(value))

    def _deserialize_identifier(self, value: str) -> IdentifierRule:
        return IdentifierRule([NAME(value)])

    def _deserialize_string(self, value: str) -> StringRule:
        result = []
        # split string into individual parts based on lark grammar
        # e.g. 'aaa$${bbb}ccc${"ddd-${eee}"}' -> ['aaa', '$${bbb}', 'ccc', '${"ddd-${eee}"}']
        # 'aa-${"bb-${"cc-${"dd-${5 + 5}"}"}"}' -> ['aa-', '${"bb-${"cc-${"dd-${5 + 5}"}"}"}']
        pattern = regex.compile(r"(\${1,2}\{(?:[^{}]|(?R))*\})")
        parts = [part for part in pattern.split(value) if part != ""]

        for part in parts:
            if part == '"':
                continue

            if part.startswith('"'):
                part = part[1:]
            if part.endswith('"'):
                part = part[:-1]

            e = self._deserialize_string_part(part)
            result.append(e)

        return StringRule([DBLQUOTE(), *result, DBLQUOTE()])

    def _deserialize_string_part(self, value: str) -> StringPartRule:
        if value.startswith("$${") and value.endswith("}"):
            return StringPartRule([ESCAPED_INTERPOLATION(value)])

        if value.startswith("${") and value.endswith("}"):
            return StringPartRule(
                [
                    InterpolationRule(
                        [INTERP_START(), self._deserialize_expression(value), RBRACE()]
                    )
                ]
            )

        return StringPartRule([STRING_CHARS(value)])

    def _deserialize_heredoc(
        self, value: str, trim: bool
    ) -> Union[HeredocTemplateRule, HeredocTrimTemplateRule]:
        if trim:
            return HeredocTrimTemplateRule([HEREDOC_TRIM_TEMPLATE(value)])
        return HeredocTemplateRule([HEREDOC_TEMPLATE(value)])

    def _deserialize_expression(self, value: str) -> ExprTermRule:
        """Deserialize an expression string into an ExprTermRule."""
        # instead of processing expression manually and trying to recognize what kind of expression it is,
        #   turn it into HCL2 code and parse it with lark:

        # unwrap from ${ and }
        value = value[2:-1]
        # create HCL2 snippet
        value = f"temp = {value}"
        # parse the above
        parsed_tree = parses(value)
        # transform parsed tree into LarkElement tree
        rules_tree = self._transformer.transform(parsed_tree)
        # extract expression from the tree
        result = rules_tree.body.children[0].expression

        return result

    def _deserialize_block(self, first_label: str, value: dict) -> BlockRule:
        """Deserialize a block by extracting labels and body"""
        labels = [first_label]
        body = value

        # Keep peeling off single-key layers until we hit the body (dict with IS_BLOCK)
        while isinstance(body, dict) and not body.get(IS_BLOCK):
            non_block_keys = [k for k in body.keys() if k != IS_BLOCK]
            if len(non_block_keys) == 1:
                # This is another label level
                label = non_block_keys[0]
                labels.append(label)
                body = body[label]
            else:
                # Multiple keys = this is the body
                break

        return BlockRule(
            [
                *[self._deserialize(label) for label in labels],
                LBRACE(),
                self._deserialize(body),
                RBRACE(),
            ]
        )

    def _deserialize_attribute(self, name: str, value: Any) -> AttributeRule:
        expr_term = self._deserialize(value)

        if not isinstance(expr_term, ExprTermRule):
            expr_term = ExprTermRule([expr_term])

        children = [
            self._deserialize_identifier(name),
            EQ(),
            expr_term,
        ]
        return AttributeRule(children)

    def _deserialize_list(self, value: List) -> TupleRule:
        children = []
        for element in value:
            deserialized = self._deserialize(element)
            if not isinstance(deserialized, ExprTermRule):
                # whatever an element of the list is, it has to be nested inside ExprTermRule
                deserialized = ExprTermRule([deserialized])
            children.append(deserialized)
            children.append(COMMA())

        return TupleRule([LSQB(), *children, RSQB()])

    def _deserialize_object(self, value: dict) -> ObjectRule:
        children = []
        for key, value in value.items():
            children.append(self._deserialize_object_elem(key, value))

            if self.options.object_elements_trailing_comma:
                children.append(COMMA())

        return ObjectRule([LBRACE(), *children, RBRACE()])

    def _deserialize_object_elem(self, key: str, value: Any) -> ObjectElemRule:
        if self._is_expression(key):
            key = ObjectElemKeyExpressionRule(
                [
                    child
                    for child in self._deserialize_expression(key).children
                    if child is not None
                ]
            )
        elif "." in key:
            parts = key.split(".")
            children = []
            for part in parts:
                children.append(self._deserialize_identifier(part))
                children.append(DOT())
            key = ObjectElemKeyDotAccessor(children[:-1])  # without the last comma
        else:
            key = self._deserialize_text(key)

        result = [
            ObjectElemKeyRule([key]),
            COLON() if self.options.object_elements_colon else EQ(),
            ExprTermRule([self._deserialize(value)]),
        ]

        return ObjectElemRule(result)

    def _is_expression(self, value: str) -> bool:
        return value.startswith("${") and value.endswith("}")

    def _is_block(self, value: Any) -> bool:
        """Simple check: if it's a list containing dicts with IS_BLOCK markers"""
        if not isinstance(value, list) or len(value) == 0:
            return False

        # Check if any item in the list has IS_BLOCK marker (directly or nested)
        for item in value:
            if isinstance(item, dict) and self._contains_block_marker(item):
                return True

        return False

    def _contains_block_marker(self, obj: dict) -> bool:
        """Recursively check if a dict contains IS_BLOCK marker anywhere"""
        if obj.get(IS_BLOCK):
            return True
        for value in obj.values():
            if isinstance(value, dict) and self._contains_block_marker(value):
                return True
            if isinstance(value, list):
                for element in value:
                    if self._contains_block_marker(element):
                        return True
        return False
