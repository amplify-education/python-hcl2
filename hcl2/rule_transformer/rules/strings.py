import sys
from typing import Tuple, List, Any, Union

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.expressions import ExpressionRule
from hcl2.rule_transformer.rules.tokens import (
    INTERP_START,
    RBRACE,
    DBLQUOTE,
    STRING_CHARS,
    ESCAPED_INTERPOLATION,
    HEREDOC_TEMPLATE, 
    HEREDOC_TRIM_TEMPLATE,
)
from hcl2.rule_transformer.utils import (
    SerializationOptions,
    SerializationContext,
    to_dollar_string,
    HEREDOC_TRIM_PATTERN, 
    HEREDOC_PATTERN,
)


class InterpolationRule(LarkRule):

    _children: Tuple[
        INTERP_START,
        ExpressionRule,
        RBRACE,
    ]

    @staticmethod
    def lark_name() -> str:
        return "interpolation"

    @property
    def expression(self):
        return self.children[1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return to_dollar_string(self.expression.serialize(options))


class StringPartRule(LarkRule):
    _children: Tuple[Union[STRING_CHARS, ESCAPED_INTERPOLATION, InterpolationRule]]

    @staticmethod
    def lark_name() -> str:
        return "string_part"

    @property
    def content(self) -> Union[STRING_CHARS, ESCAPED_INTERPOLATION, InterpolationRule]:
        return self._children[0]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return self.content.serialize(options, context)


class StringRule(LarkRule):

    _children: Tuple[DBLQUOTE, List[StringPartRule], DBLQUOTE]

    @staticmethod
    def lark_name() -> str:
        return "string"

    @property
    def string_parts(self):
        return self.children[1:-1]

    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        return '"' + "".join(part.serialize() for part in self.string_parts) + '"'


class HeredocTemplateRule(LarkRule):
    
    _children: Tuple[HEREDOC_TEMPLATE]
    _trim_chars = "\n\t "
    
    
    @staticmethod
    def lark_name() -> str:
        return "heredoc_template"
    
    @property
    def heredoc(self):
        return self.children[0]
    
    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        heredoc = self.heredoc.serialize(options, context)
        
        if not options.preserve_heredocs:
            match = HEREDOC_PATTERN.match(heredoc)
            if not match:
                raise RuntimeError(f"Invalid Heredoc token: {heredoc}")
            heredoc = match.group(2)
        
        result = heredoc.rstrip(self._trim_chars)
        return f'"{result}"'


class HeredocTrimTemplateRule(HeredocTemplateRule):

    _children: Tuple[HEREDOC_TRIM_TEMPLATE]
    
    @staticmethod
    def lark_name() -> str:
        return "heredoc_trim_template"
    
    def serialize(
        self, options=SerializationOptions(), context=SerializationContext()
    ) -> Any:
        # See https://github.com/hashicorp/hcl2/blob/master/hcl/hclsyntax/spec.md#template-expressions
        # This is a special version of heredocs that are declared with "<<-"
        # This will calculate the minimum number of leading spaces in each line of a heredoc
        # and then remove that number of spaces from each line

        heredoc = self.heredoc.serialize(options, context)

        if not options.preserve_heredocs:
            match = HEREDOC_TRIM_PATTERN.match(heredoc)
            if not match:
                raise RuntimeError(f"Invalid Heredoc token: {heredoc}")
            heredoc = match.group(2)

        heredoc = heredoc.rstrip(self._trim_chars)  
        lines = heredoc.split("\n")
    
        # calculate the min number of leading spaces in each line
        min_spaces = sys.maxsize
        for line in lines:
            leading_spaces = len(line) - len(line.lstrip(" "))
            min_spaces = min(min_spaces, leading_spaces)
    
        # trim off that number of leading spaces from each line
        lines = [line[min_spaces:] for line in lines]
        return '"' + "\n".join(lines) + '"'
    