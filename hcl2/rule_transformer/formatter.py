from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from hcl2.rule_transformer.rules.abstract import LarkElement
from hcl2.rule_transformer.rules.base import (
    StartRule,
    BlockRule,
    AttributeRule,
    BodyRule,
)
from hcl2.rule_transformer.rules.containers import ObjectRule, ObjectElemRule, TupleRule
from hcl2.rule_transformer.rules.expressions import ExprTermRule, ExpressionRule
from hcl2.rule_transformer.rules.for_expressions import (
    ForTupleExprRule,
    ForObjectExprRule,
)
from hcl2.rule_transformer.rules.tokens import NL_OR_COMMENT, LBRACE, COLON, LSQB, COMMA
from hcl2.rule_transformer.rules.whitespace import NewLineOrCommentRule


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
        self._current_line = 1
        self._current_indent_level = 0

    def format_tree(self, tree: LarkElement):
        if isinstance(tree, StartRule):
            self.format_start_rule(tree)

    def format_start_rule(self, rule: StartRule):
        self.format_body_rule(rule.body, 0)
        # for child in rule.body.children:
        #     if isinstance(child, BlockRule):
        #         self.format_block_rule(child, 1)

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
            self.format_expression(rule.expression)

    def format_fortupleexpr(self, expression: ForTupleExprRule, indent_level: int = 0):
        for child in expression.children:
            if isinstance(child, ExprTermRule):
                self.format_expression(child, indent_level + 1)

        indexes = [1, 3, 5, 7]
        for index in indexes:
            expression.children[index] = self._build_newline(indent_level)
        self._deindent_last_line()
        # expression.children[8] = self._build_newline(indent_level - 1)

    def format_forobjectexpr(
        self, expression: ForObjectExprRule, indent_level: int = 0
    ):
        for child in expression.children:
            if isinstance(child, ExprTermRule):
                self.format_expression(child, indent_level + 1)

        indexes = [1, 3, 12]
        for index in indexes:
            expression.children[index] = self._build_newline(indent_level)

        self._deindent_last_line()

    def _vertically_align_attributes_in_body(self, body: BodyRule):
        attributes_sequence: List[AttributeRule] = []

        for child in body.children:
            if isinstance(child, AttributeRule):
                attributes_sequence.append(child)

            elif attributes_sequence:
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
                attributes_sequence = []

    def _vertically_align_object_elems(self, rule: ObjectRule):
        max_length = max(len(elem.key.serialize()) for elem in rule.elements)
        for elem in rule.elements:
            key_length = len(elem.key.serialize())
            print(elem.key.serialize(), key_length)

            spaces_to_add = max_length - key_length

            separator = elem.children[1]
            if isinstance(separator, COLON):
                spaces_to_add += 1

            elem.children[1].set_value(" " * spaces_to_add + separator.value)

    def _move_to_next_line(self, times: int = 1):
        self._current_line += times

    def _increase_indent_level(self, times: int = 1):
        self._current_indent_level += times

    def _decrease_indent_level(self, times: int = 1):
        self._current_indent_level -= times
        if self._current_indent_level < 0:
            self._current_indent_level = 0

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

    # def _build_meta(self, indent_level: int = 0, length: int = 0) -> Meta:
    #     result = Meta()
    #     result.empty = length == 0
    #     result.line = self._current_line
    #     result.column = indent_level * self.options.indent_length
    #     # result.start_pos =
    #     # result.end_line =
    #     # result.end_column =
    #     # result.end_pos =
    #     # result.orig_expansion =
    #     # result.match_tree =
    #     return result
