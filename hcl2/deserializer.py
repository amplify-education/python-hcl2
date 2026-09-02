"""Deserialize Python dicts (or JSON) into LarkElement trees."""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Any, List, Optional, TextIO, Union

from regex import regex

from hcl2.const import COMMENTS_KEY, INLINE_COMMENTS_KEY, IS_BLOCK
from hcl2.parser import parser as _get_parser
from hcl2.rules.abstract import LarkElement, LarkRule
from hcl2.rules.base import (
    AttributeRule,
    BlockRule,
    BodyRule,
    StartRule,
)
from hcl2.rules.containers import (
    ObjectElemKeyExpressionRule,
    ObjectElemKeyRule,
    ObjectElemRule,
    ObjectRule,
    TupleRule,
)
from hcl2.rules.expressions import ExprTermRule
from hcl2.rules.literal_rules import (
    FloatLitRule,
    IdentifierRule,
    IntLitRule,
    LiteralValueRule,
)
from hcl2.rules.strings import (
    HeredocTemplateRule,
    HeredocTrimTemplateRule,
    InterpolationRule,
    StringPartRule,
    StringRule,
)
from hcl2.rules.tokens import (
    COLON,
    COMMA,
    DBLQUOTE,
    EQ,
    ESCAPED_INTERPOLATION,
    FALSE,
    HEREDOC_TEMPLATE,
    HEREDOC_TRIM_TEMPLATE,
    INTERP_START,
    LBRACE,
    LSQB,
    NAME,
    NULL,
    RBRACE,
    RSQB,
    STRING_CHARS,
    TRUE,
    FloatLiteral,
    IntLiteral,
)
from hcl2.template import INTERPOLATION, map_literal_spans, split_template
from hcl2.transformer import RuleTransformer
from hcl2.utils import HEREDOC_PATTERN, HEREDOC_TRIM_PATTERN, process_escape_sequences


def _unescape_heredoc_body(inner: str) -> str:
    r"""Resolve a quoted string's escapes for a body that interprets none.

    A heredoc body is read literally, so anything the quoted form spelled as
    an escape has to become the character itself: `\t` a tab, `\u00e9` an
    accented e. `process_escape_sequences` is the package's one implementation
    of that alphabet, and using it here is what stops this path from resolving
    a shorter list than the reader does.

    Only in literal spans. Inside `${...}` the text is expression source, and
    an escape there belongs to a string literal written inside the expression:
    OpenTofu reads `"${upper("a\"b")}"` as `A"B`, so resolving that `\"` would
    close the nested literal early and change what the expression says.
    """
    return map_literal_spans(inner, process_escape_sequences)


# A line that could end a heredoc: the delimiter word alone, give or take
# surrounding spaces and tabs -- and a carriage return, because the body is
# split on "\n" and a CRLF line hands back its own `\r`. OpenTofu ends a
# heredoc on `EOF\r` exactly as it does on `EOF `, so a CRLF body carrying
# the delimiter has to count.
_CLOSING_MARKER_LINE = re.compile(r"[ \t]*([a-zA-Z][a-zA-Z0-9._-]*)[ \t\r]*")


def _heredoc_delimiter(content: str) -> str:
    """Return a delimiter the body does not close on its own.

    `EOF` unless the body holds a line that would end the heredoc there, in
    which case a numbered variant is used. The word matters: a log excerpt, a
    shell script or an embedded config is exactly the sort of value people put
    in a heredoc, and `EOF` is exactly the word such a payload tends to
    contain. Writing one blindly produced a file that no longer parsed.
    """
    occupied = set()
    for line in content.split("\n"):
        match = _CLOSING_MARKER_LINE.fullmatch(line)
        if match is not None:
            occupied.add(match.group(1))

    if "EOF" not in occupied:
        return "EOF"

    suffix = 1
    while f"EOF_{suffix}" in occupied:
        suffix += 1
    return f"EOF_{suffix}"


def _interpolation_spans(text: str) -> List[str]:
    """The `${...}` and `%{...}` spans of *text*, in order."""
    return [chunk for kind, chunk in split_template(text) if kind == INTERPOLATION]


def _expressible_as_heredoc(content: str, source: str) -> bool:
    """Whether *content* can be a heredoc body without changing.

    A heredoc body is read literally, so it can hold a carriage return only
    where one ends a line. A lone `\r` makes the file unreadable rather than
    merely different: OpenTofu rejects `<<EOF\nx\ry\nEOF` with "No closing
    marker was found for the string", while the quoted `"x\ry\n"` it came
    from is valid and evaluates to that carriage return. Such a value stays
    quoted, for the same reason one that does not end in a newline does.
    """
    if "\r" in content.replace("\r\n", ""):
        return False

    # Resolving escapes can spell a sigil that was not there. `"\u0024\u007bfoo\u007d"`
    # is the six literal characters `${foo}` to Terraform -- escapes resolve at
    # token level and the result is not rescanned -- but written into a heredoc
    # body, which is not escaped at all, those characters are a live
    # interpolation. The reverse happens too: `\u0024${b}` resolves to `$${b}`,
    # demoting an interpolation to escaped text. Either way the value changes,
    # so it stays quoted.
    return _interpolation_spans(source) == _interpolation_spans(content)


@dataclass
class DeserializerOptions:
    """Options controlling how Python dicts are deserialized into LarkElement trees."""

    # Convert heredoc values (<<EOF...EOF) to regular escaped strings during
    # deserialization. When False, heredoc syntax is preserved as-is.
    heredocs_to_strings: bool = False
    # Convert newline-terminated escaped strings back into heredoc syntax
    # (<<EOF...EOF) during deserialization. A value that does not end in a
    # newline is left quoted: a non-empty heredoc body always does, so writing
    # one as a heredoc would hand back a different value on the next read.
    strings_to_heredocs: bool = False
    # Use colon (:) instead of equals (=) as the separator in object elements.
    object_elements_colon: bool = False
    # Append a trailing comma after each object element.
    object_elements_trailing_comma: bool = True
    # with_comments: bool = False # TODO


class LarkElementTreeDeserializer(ABC):
    """Abstract base for deserializers that produce LarkElement trees."""

    def __init__(self, options: Optional[DeserializerOptions] = None):
        self.options = options or DeserializerOptions()

    @abstractmethod
    def loads(self, value: str) -> LarkElement:
        """Deserialize a JSON string into a LarkElement tree."""
        raise NotImplementedError()

    def load(self, file: TextIO) -> LarkElement:
        """Deserialize a JSON file into a LarkElement tree."""
        return self.loads(file.read())


class BaseDeserializer(LarkElementTreeDeserializer):
    """Default deserializer: Python dict/JSON → LarkElement tree."""

    @cached_property
    def _transformer(self) -> RuleTransformer:
        return RuleTransformer()

    def load_python(self, value: Any) -> StartRule:
        """Deserialize a Python object into a StartRule tree."""
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict for top-level HCL body, got {type(value).__name__}")
        # Top-level dict is always a body (attributes + blocks), not an object
        children = self._deserialize_block_elements(value)
        return StartRule([BodyRule(children)])

    def loads(self, value: str) -> LarkElement:
        """Deserialize a JSON string into a LarkElement tree."""
        return self.load_python(json.loads(value))

    def _deserialize(self, value: Any) -> LarkElement:
        if isinstance(value, dict):
            if self._contains_block_marker(value):
                children: List[Any] = []

                block_elements = self._deserialize_block_elements(value)
                for element in block_elements:
                    children.append(element)

                return BodyRule(children)

            return self._deserialize_object(value)

        if isinstance(value, list):
            return self._deserialize_list(value)

        return self._deserialize_text(value)

    def _deserialize_block_elements(self, value: dict) -> List[LarkElement]:
        children: List[LarkElement] = []
        for key, val in value.items():
            if self._is_block(val):
                # this value is a list of blocks, iterate over each block and deserialize them
                for block in val:
                    children.append(self._deserialize_block(key, block))

            else:
                # otherwise it's just an attribute
                if not self._is_reserved_key(key):
                    children.append(self._deserialize_attribute(key, val))

        return children

    # pylint: disable=R0911
    def _deserialize_text(self, value: Any) -> LarkRule:
        # bool must be checked before int since bool is a subclass of int
        if isinstance(value, bool):
            if value:
                return LiteralValueRule([TRUE()])
            return LiteralValueRule([FALSE()])

        if value is None:
            return LiteralValueRule([NULL()])

        if isinstance(value, float):
            return FloatLitRule([FloatLiteral(value)])

        if isinstance(value, int):
            return IntLitRule([IntLiteral(value)])

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

                if self.options.strings_to_heredocs:
                    content = _unescape_heredoc_body(value[1:-1])
                    # A heredoc's closing marker sits on a line of its own, so
                    # any body with content in it ends with a newline. A value
                    # that does not cannot be written as one without gaining
                    # that character, so it stays a quoted string.
                    #
                    # The empty string is the one value this excludes that a
                    # heredoc could in fact express -- `<<EOF\nEOF` evaluates
                    # to "" in Terraform and here. It stays quoted anyway,
                    # because `x = ""` says the same thing in one line.
                    if content.endswith("\n") and _expressible_as_heredoc(content, value[1:-1]):
                        return self._deserialize_string_as_heredoc(content)

                return self._deserialize_string(value)

            if self._is_expression(value):
                return self._deserialize_expression(value)

            return self._deserialize_identifier(value)

        return self._deserialize_identifier(str(value))

    def _deserialize_identifier(self, value: str) -> IdentifierRule:
        return IdentifierRule([NAME(value)])

    def _deserialize_string(self, value: str) -> StringRule:
        # If the string contains template directives, delegate to parser
        inner = value[1:-1] if value.startswith('"') and value.endswith('"') else value
        # Check for unescaped %{ (i.e. %{ not preceded by another %)
        stripped = inner.replace("%%{", "")
        if "%{" in stripped:
            return self._deserialize_string_via_parser(value)

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

            string_part = self._deserialize_string_part(part)
            result.append(string_part)

        return StringRule([DBLQUOTE(), *result, DBLQUOTE()])

    def _deserialize_string_via_parser(self, value: str) -> StringRule:
        """Deserialize a string containing template directives by parsing it."""
        # Ensure the value is quoted
        if not (value.startswith('"') and value.endswith('"')):
            value = f'"{value}"'
        snippet = f"temp = {value}"
        parsed_tree = _get_parser().parse(snippet)
        rules_tree = self._transformer.transform(parsed_tree)
        # Extract the string from: start -> body -> attribute -> expression -> string
        expr = rules_tree.body.children[0].expression
        # The expression is an ExprTermRule wrapping a StringRule
        for child in expr.children:
            if isinstance(child, StringRule):
                return child
        # Fallback: shouldn't happen, but return as-is
        return expr  # type: ignore[return-value]

    def _deserialize_string_part(self, value: str) -> StringPartRule:
        if value.startswith("$${") and value.endswith("}"):
            return StringPartRule([ESCAPED_INTERPOLATION(value)])

        if value.startswith("${") and value.endswith("}"):
            return StringPartRule(
                [InterpolationRule([INTERP_START(), self._deserialize_expression(value), RBRACE()])]
            )

        return StringPartRule([STRING_CHARS(value)])

    def _deserialize_heredoc(
        self, value: str, trim: bool
    ) -> Union[HeredocTemplateRule, HeredocTrimTemplateRule]:
        if trim:
            return HeredocTrimTemplateRule([HEREDOC_TRIM_TEMPLATE(value)])
        return HeredocTemplateRule([HEREDOC_TEMPLATE(value)])

    def _deserialize_string_as_heredoc(self, content: str) -> HeredocTemplateRule:
        """Wrap an unescaped body, already newline-terminated, in heredoc syntax."""
        delimiter = _heredoc_delimiter(content)
        heredoc = f"<<{delimiter}\n{content}{delimiter}"
        return HeredocTemplateRule([HEREDOC_TEMPLATE(heredoc)])

    def _deserialize_expression(self, value: str) -> ExprTermRule:
        """Deserialize an expression string into an ExprTermRule."""
        # instead of processing expression manually and trying to recognize what kind of expression it is,
        #   turn it into HCL2 code and parse it with lark:

        # unwrap from ${ and }
        value = value[2:-1]
        # create HCL2 snippet
        value = f"temp = {value}"
        # parse the above
        parsed_tree = _get_parser().parse(value)
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
            non_block_keys = [k for k in body.keys() if not self._is_reserved_key(k)]
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
        children: List[Any] = []
        for element in value:
            deserialized = self._deserialize(element)
            if not isinstance(deserialized, ExprTermRule):
                # whatever an element of the list is, it has to be nested inside ExprTermRule
                deserialized = ExprTermRule([deserialized])
            children.append(deserialized)
            children.append(COMMA())

        return TupleRule([LSQB(), *children, RSQB()])

    def _deserialize_object(self, value: dict) -> ObjectRule:
        children: List[Any] = []
        for key, val in value.items():
            children.append(self._deserialize_object_elem(key, val))

            if self.options.object_elements_trailing_comma:
                children.append(COMMA())

        return ObjectRule([LBRACE(), *children, RBRACE()])

    def _deserialize_object_elem(self, key: Any, value: Any) -> ObjectElemRule:
        key_rule: Union[ObjectElemKeyExpressionRule, ObjectElemKeyRule]

        if self._is_expression(key):
            expr = self._deserialize_expression(key)
            key_rule = ObjectElemKeyExpressionRule([expr])
        else:
            key = self._deserialize_text(key)
            key_rule = ObjectElemKeyRule([key])

        result = [
            key_rule,
            COLON() if self.options.object_elements_colon else EQ(),
            ExprTermRule([self._deserialize(value)]),
        ]

        return ObjectElemRule(result)

    def _is_reserved_key(self, key: str) -> bool:
        """Check if a key is a reserved metadata key that should be skipped during deserialization."""
        return key in (IS_BLOCK, COMMENTS_KEY, INLINE_COMMENTS_KEY)

    def _is_expression(self, value: Any) -> bool:
        return isinstance(value, str) and value.startswith("${") and value.endswith("}")

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
                    if isinstance(element, dict) and self._contains_block_marker(element):
                        return True
        return False
