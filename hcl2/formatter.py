from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from hcl2.rules.abstract import LarkElement
from hcl2.rules.base import (
    StartRule,
    BlockRule,
    AttributeRule,
    BodyRule,
)
from hcl2.rules.containers import ObjectRule, ObjectElemRule, TupleRule
from hcl2.rules.expressions import ExprTermRule, ExpressionRule
from hcl2.rules.for_expressions import (
    ForTupleExprRule,
    ForObjectExprRule,
    ForIntroRule,
    ForCondRule,
)
from hcl2.rules.tokens import NL_OR_COMMENT, LBRACE, COLON, LSQB, COMMA
from hcl2.rules.whitespace import NewLineOrCommentRule


@dataclass
class FormatterOptions:
    indent_length: int = 2
    open_empty_blocks: bool = True
    open_empty_objects: bool = True
    open_empty_tuples: bool = False

    vertically_align_attributes: bool = True
    vertically_align_object_elements: bool = True


class LarkElementTreeFormatter(ABC):
    def __init__(self, options: FormatterOptions = None):
        self.options = options or FormatterOptions()

    @abstractmethod
    def format_tree(self, tree: LarkElement):
        raise NotImplementedError()


class BaseFormatter(LarkElementTreeFormatter):
    def __init__(self, options: FormatterOptions = None):
        super().__init__(options)
        self._last_new_line: NewLineOrCommentRule = None

    def format_tree(self, tree: LarkElement):
        if isinstance(tree, StartRule):
            self.format_start_rule(tree)

    def format_start_rule(self, rule: StartRule):
        self.format_body_rule(rule.body, 0)

    def format_block_rule(self, rule: BlockRule, indent_level: int = 0):
        if self.options.vertically_align_attributes:
            self._vertically_align_attributes_in_body(rule.body)

        self.format_body_rule(rule.body, indent_level)
        if len(rule.body.children) > 0:
            rule.children.insert(-1, self._build_newline(indent_level - 1))
        elif self.options.open_empty_blocks:
            rule.children.insert(-1, self._build_newline(indent_level - 1, 2))

    def format_body_rule(self, rule: BodyRule, indent_level: int = 0):

        in_start = isinstance(rule.parent, StartRule)

        new_children = []
        if not in_start:
            new_children.append(self._build_newline(indent_level))

        for i, child in enumerate(rule.children):
            new_children.append(child)

            if isinstance(child, AttributeRule):
                self.format_attribute_rule(child, indent_level)
                new_children.append(self._build_newline(indent_level))

            if isinstance(child, BlockRule):
                self.format_block_rule(child, indent_level + 1)

                if i > 0:
                    new_children.insert(-2, self._build_newline(indent_level))
                new_children.append(self._build_newline(indent_level, 2))

        if new_children:
            new_children.pop(-1)
        rule._children = new_children

    def format_attribute_rule(self, rule: AttributeRule, indent_level: int = 0):
        self.format_expression(rule.expression, indent_level + 1)

    def format_tuple_rule(self, rule: TupleRule, indent_level: int = 0):
        if len(rule.elements) == 0:
            if self.options.open_empty_tuples:
                rule.children.insert(1, self._build_newline(indent_level - 1, 2))
            return

        new_children = []
        for child in rule.children:
            new_children.append(child)
            if isinstance(child, ExprTermRule):
                self.format_expression(child, indent_level + 1)

            if isinstance(child, (COMMA, LSQB)):
                new_children.append(self._build_newline(indent_level))

        self._deindent_last_line()
        rule._children = new_children

    def format_object_rule(self, rule: ObjectRule, indent_level: int = 0):
        if len(rule.elements) == 0:
            if self.options.open_empty_objects:
                rule.children.insert(1, self._build_newline(indent_level - 1, 2))
            return

        new_children = []
        for i in range(len(rule.children)):
            child = rule.children[i]
            next_child = rule.children[i + 1] if i + 1 < len(rule.children) else None
            new_children.append(child)

            if isinstance(child, LBRACE):
                new_children.append(self._build_newline(indent_level))

            if (
                next_child
                and isinstance(next_child, ObjectElemRule)
                and isinstance(child, (ObjectElemRule, COMMA))
            ):
                new_children.append(self._build_newline(indent_level))

            if isinstance(child, ObjectElemRule):
                self.format_expression(child.expression, indent_level + 1)

        new_children.insert(-1, self._build_newline(indent_level))
        self._deindent_last_line()

        rule._children = new_children

        if self.options.vertically_align_object_elements:
            self._vertically_align_object_elems(rule)

    def format_expression(self, rule: ExprTermRule, indent_level: int = 0):
        if isinstance(rule.expression, ObjectRule):
            self.format_object_rule(rule.expression, indent_level)

        elif isinstance(rule.expression, TupleRule):
            self.format_tuple_rule(rule.expression, indent_level)

        elif isinstance(rule.expression, ForTupleExprRule):
            self.format_fortupleexpr(rule.expression, indent_level)

        elif isinstance(rule.expression, ForObjectExprRule):
            self.format_forobjectexpr(rule.expression, indent_level)

        elif isinstance(rule.expression, ExprTermRule):
            self.format_expression(rule.expression, indent_level)

    def format_fortupleexpr(self, expression: ForTupleExprRule, indent_level: int = 0):
        for child in expression.children:
            if isinstance(child, ExprTermRule):
                self.format_expression(child, indent_level + 1)
            elif isinstance(child, (ForIntroRule, ForCondRule)):
                for sub_child in child.children:
                    if isinstance(sub_child, ExprTermRule):
                        self.format_expression(sub_child, indent_level + 1)

        for index in [1, 3]:
            expression.children[index] = self._build_newline(indent_level)

        if expression.condition is not None:
            expression.children[5] = self._build_newline(indent_level)
        else:
            expression.children[5] = None

        expression.children[7] = self._build_newline(indent_level)
        self._deindent_last_line()

    def format_forobjectexpr(
        self, expression: ForObjectExprRule, indent_level: int = 0
    ):
        for child in expression.children:
            if isinstance(child, ExprTermRule):
                self.format_expression(child, indent_level + 1)
            elif isinstance(child, (ForIntroRule, ForCondRule)):
                for sub_child in child.children:
                    if isinstance(sub_child, ExprTermRule):
                        self.format_expression(sub_child, indent_level + 1)

        for index in [1, 3]:
            expression.children[index] = self._build_newline(indent_level)

        expression.children[6] = None
        expression.children[8] = None

        if expression.condition is not None:
            expression.children[10] = self._build_newline(indent_level)
        else:
            expression.children[10] = None

        expression.children[12] = self._build_newline(indent_level)
        self._deindent_last_line()

    def _vertically_align_attributes_in_body(self, body: BodyRule):
        attributes_sequence: List[AttributeRule] = []

        for child in body.children:
            if isinstance(child, AttributeRule):
                attributes_sequence.append(child)

            elif attributes_sequence:
                self._align_attributes_sequence(attributes_sequence)
                attributes_sequence = []

        if attributes_sequence:
            self._align_attributes_sequence(attributes_sequence)

    def _align_attributes_sequence(self, attributes_sequence: List[AttributeRule]):
        max_length = max(
            len(attribute.identifier.token.value)
            for attribute in attributes_sequence
        )
        for attribute in attributes_sequence:
            name_length = len(attribute.identifier.token.value)
            spaces_to_add = max_length - name_length
            attribute.children[1].set_value(
                " " * spaces_to_add + attribute.children[1].value
            )

    def _vertically_align_object_elems(self, rule: ObjectRule):
        max_length = max(len(elem.key.serialize()) for elem in rule.elements)
        for elem in rule.elements:
            key_length = len(elem.key.serialize())

            spaces_to_add = max_length - key_length

            separator = elem.children[1]
            if isinstance(separator, COLON):
                spaces_to_add += 1

            elem.children[1].set_value(" " * spaces_to_add + separator.value)

    def _build_newline(
        self, next_line_indent: int = 0, count: int = 1
    ) -> NewLineOrCommentRule:
        result = NewLineOrCommentRule(
            [
                NL_OR_COMMENT(
                    ("\n" * count) + " " * self.options.indent_length * next_line_indent
                )
            ]
        )
        self._last_new_line = result
        return result

    def _deindent_last_line(self, times: int = 1):
        token = self._last_new_line.token
        for i in range(times):
            if token.value.endswith(" " * self.options.indent_length):
                token.set_value(token.value[: -self.options.indent_length])
