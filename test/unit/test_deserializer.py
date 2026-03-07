# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.const import IS_BLOCK, COMMENTS_KEY
from hcl2.deserializer import BaseDeserializer, DeserializerOptions
from hcl2.rules.base import StartRule, BodyRule, BlockRule, AttributeRule
from hcl2.rules.containers import (
    TupleRule,
    ObjectRule,
    ObjectElemRule,
    ObjectElemKeyExpressionRule,
)
from hcl2.rules.expressions import ExprTermRule
from hcl2.rules.literal_rules import IdentifierRule, IntLitRule, FloatLitRule
from hcl2.rules.strings import (
    StringRule,
    StringPartRule,
    InterpolationRule,
    HeredocTemplateRule,
    HeredocTrimTemplateRule,
)
from hcl2.rules.tokens import (
    STRING_CHARS,
    ESCAPED_INTERPOLATION,
    COMMA,
    EQ,
    COLON,
)


# --- helpers ---


def _deser(options=None):
    return BaseDeserializer(options)


# --- DeserializerOptions tests ---


class TestDeserializerOptions(TestCase):
    def test_defaults(self):
        opts = DeserializerOptions()
        self.assertFalse(opts.heredocs_to_strings)
        self.assertFalse(opts.strings_to_heredocs)
        self.assertFalse(opts.object_elements_colon)
        self.assertTrue(opts.object_elements_trailing_comma)


# --- load_python top-level dispatch ---


class TestBaseDeserializerLoadPython(TestCase):
    def test_dict_input_produces_start_with_body(self):
        d = _deser()
        result = d.load_python({"x": 1})
        self.assertIsInstance(result, StartRule)
        self.assertIsInstance(result.body, BodyRule)

    def test_dict_body_contains_attribute(self):
        d = _deser()
        result = d.load_python({"x": 1})
        body = result.body
        self.assertEqual(len(body.children), 1)
        self.assertIsInstance(body.children[0], AttributeRule)

    def test_list_input_produces_start_wrapping_tuple(self):
        d = _deser()
        result = d.load_python([1, 2])
        self.assertIsInstance(result, StartRule)
        # The child should be a TupleRule (via _deserialize)
        child = result.children[0]
        self.assertIsInstance(child, TupleRule)

    def test_scalar_string_input(self):
        d = _deser()
        result = d.load_python("hello")
        self.assertIsInstance(result, StartRule)
        child = result.children[0]
        self.assertIsInstance(child, IdentifierRule)
        self.assertEqual(child.token.value, "hello")

    def test_loads_parses_json(self):
        d = _deser()
        result = d.loads('{"key": 42}')
        self.assertIsInstance(result, StartRule)
        body = result.body
        self.assertEqual(len(body.children), 1)
        self.assertIsInstance(body.children[0], AttributeRule)


# --- _deserialize_text branches ---


class TestDeserializeText(TestCase):
    def test_bool_true(self):
        d = _deser()
        result = d._deserialize_text(True)
        self.assertIsInstance(result, IdentifierRule)
        self.assertEqual(result.token.value, "true")

    def test_bool_false(self):
        d = _deser()
        result = d._deserialize_text(False)
        self.assertIsInstance(result, IdentifierRule)
        self.assertEqual(result.token.value, "false")

    def test_bool_before_int(self):
        """bool is subclass of int; ensure True doesn't produce IntLitRule."""
        d = _deser()
        result = d._deserialize_text(True)
        self.assertNotIsInstance(result, IntLitRule)
        self.assertIsInstance(result, IdentifierRule)

    def test_int_value(self):
        d = _deser()
        result = d._deserialize_text(42)
        self.assertIsInstance(result, IntLitRule)
        self.assertEqual(result.token.value, 42)

    def test_float_value(self):
        d = _deser()
        result = d._deserialize_text(3.14)
        self.assertIsInstance(result, FloatLitRule)
        self.assertEqual(result.token.value, 3.14)

    def test_quoted_string(self):
        d = _deser()
        result = d._deserialize_text('"hello"')
        self.assertIsInstance(result, StringRule)

    def test_unquoted_string_identifier(self):
        d = _deser()
        result = d._deserialize_text("my_var")
        self.assertIsInstance(result, IdentifierRule)
        self.assertEqual(result.token.value, "my_var")

    def test_expression_string(self):
        d = _deser()
        result = d._deserialize_text("${var.x}")
        self.assertIsInstance(result, ExprTermRule)

    def test_non_string_non_numeric_fallback(self):
        """Non-string, non-numeric values get str()-converted to identifier."""
        d = _deser()
        result = d._deserialize_text(None)
        self.assertIsInstance(result, IdentifierRule)
        self.assertEqual(result.token.value, "None")

    def test_zero_int(self):
        d = _deser()
        result = d._deserialize_text(0)
        self.assertIsInstance(result, IntLitRule)
        self.assertEqual(result.token.value, 0)

    def test_negative_float(self):
        d = _deser()
        result = d._deserialize_text(-1.5)
        self.assertIsInstance(result, FloatLitRule)
        self.assertEqual(result.token.value, -1.5)


# --- heredoc handling ---


class TestDeserializeHeredocs(TestCase):
    def test_preserved_heredoc(self):
        d = _deser()
        result = d._deserialize_text('"<<EOF\nhello\nEOF"')
        self.assertIsInstance(result, HeredocTemplateRule)

    def test_preserved_trim_heredoc(self):
        d = _deser()
        result = d._deserialize_text('"<<-EOF\n  hello\nEOF"')
        self.assertIsInstance(result, HeredocTrimTemplateRule)

    def test_heredocs_to_strings_skips_heredoc(self):
        opts = DeserializerOptions(heredocs_to_strings=True)
        d = _deser(opts)
        result = d._deserialize_text('"<<EOF\nhello\nEOF"')
        self.assertIsInstance(result, StringRule)

    def test_heredocs_to_strings_skips_trim_heredoc(self):
        opts = DeserializerOptions(heredocs_to_strings=True)
        d = _deser(opts)
        result = d._deserialize_text('"<<-EOF\n  hello\nEOF"')
        self.assertIsInstance(result, StringRule)

    def test_strings_to_heredocs_with_newline(self):
        opts = DeserializerOptions(strings_to_heredocs=True)
        d = _deser(opts)
        result = d._deserialize_text('"line1\\nline2"')
        self.assertIsInstance(result, HeredocTemplateRule)

    def test_strings_to_heredocs_without_newline(self):
        opts = DeserializerOptions(strings_to_heredocs=True)
        d = _deser(opts)
        result = d._deserialize_text('"no_newlines_here"')
        self.assertIsInstance(result, StringRule)


# --- _deserialize_string internals ---


class TestDeserializeString(TestCase):
    def test_plain_string(self):
        d = _deser()
        result = d._deserialize_string('"hello"')
        self.assertIsInstance(result, StringRule)
        parts = result.string_parts
        self.assertEqual(len(parts), 1)
        self.assertIsInstance(parts[0], StringPartRule)
        self.assertIsInstance(parts[0].content, STRING_CHARS)
        self.assertEqual(parts[0].content.value, "hello")

    def test_interpolation_string(self):
        d = _deser()
        result = d._deserialize_string('"${var.x}"')
        self.assertIsInstance(result, StringRule)
        parts = result.string_parts
        self.assertEqual(len(parts), 1)
        self.assertIsInstance(parts[0], StringPartRule)
        self.assertIsInstance(parts[0].content, InterpolationRule)

    def test_escaped_interpolation(self):
        d = _deser()
        result = d._deserialize_string('"$${literal}"')
        self.assertIsInstance(result, StringRule)
        parts = result.string_parts
        self.assertEqual(len(parts), 1)
        self.assertIsInstance(parts[0], StringPartRule)
        self.assertIsInstance(parts[0].content, ESCAPED_INTERPOLATION)

    def test_mixed_literal_and_interpolation(self):
        d = _deser()
        result = d._deserialize_string('"prefix-${var.x}-suffix"')
        self.assertIsInstance(result, StringRule)
        parts = result.string_parts
        self.assertEqual(len(parts), 3)
        # prefix
        self.assertIsInstance(parts[0].content, STRING_CHARS)
        self.assertEqual(parts[0].content.value, "prefix-")
        # interpolation
        self.assertIsInstance(parts[1].content, InterpolationRule)
        # suffix
        self.assertIsInstance(parts[2].content, STRING_CHARS)
        self.assertEqual(parts[2].content.value, "-suffix")

    def test_empty_string(self):
        d = _deser()
        result = d._deserialize_string('""')
        self.assertIsInstance(result, StringRule)
        # Empty string still produces one StringPartRule with empty STRING_CHARS
        self.assertEqual(len(result.string_parts), 1)
        self.assertEqual(result.string_parts[0].content.value, "")


# --- _deserialize_block label peeling ---


class TestDeserializeBlock(TestCase):
    def test_single_label_block(self):
        d = _deser()
        block_data = {"key": "val", IS_BLOCK: True}
        result = d._deserialize_block("resource", block_data)
        self.assertIsInstance(result, BlockRule)
        self.assertEqual(len(result.labels), 1)
        self.assertEqual(result.labels[0].token.value, "resource")

    def test_two_label_block(self):
        d = _deser()
        block_data = {"aws_instance": {"key": "val", IS_BLOCK: True}}
        result = d._deserialize_block("resource", block_data)
        self.assertIsInstance(result, BlockRule)
        self.assertEqual(len(result.labels), 2)
        self.assertEqual(result.labels[0].token.value, "resource")
        self.assertEqual(result.labels[1].token.value, "aws_instance")

    def test_three_label_block(self):
        d = _deser()
        block_data = {"aws_instance": {"example": {IS_BLOCK: True}}}
        result = d._deserialize_block("resource", block_data)
        self.assertIsInstance(result, BlockRule)
        self.assertEqual(len(result.labels), 3)
        self.assertEqual(result.labels[0].token.value, "resource")
        self.assertEqual(result.labels[1].token.value, "aws_instance")
        self.assertEqual(result.labels[2].token.value, "example")

    def test_multi_key_dict_stops_peeling(self):
        d = _deser()
        block_data = {"a": 1, "b": 2}
        result = d._deserialize_block("resource", block_data)
        self.assertIsInstance(result, BlockRule)
        # Should only have the first label; body is the multi-key dict
        self.assertEqual(len(result.labels), 1)
        self.assertEqual(result.labels[0].token.value, "resource")

    def test_block_body_contains_attributes(self):
        d = _deser()
        block_data = {"name": "test", IS_BLOCK: True}
        result = d._deserialize_block("resource", block_data)
        body = result.body
        self.assertIsInstance(body, BodyRule)
        # Should have one attribute (name), __is_block__ is skipped
        attrs = [c for c in body.children if isinstance(c, AttributeRule)]
        self.assertEqual(len(attrs), 1)


# --- container deserialization ---


class TestDeserializeContainers(TestCase):
    def test_list_to_tuple(self):
        d = _deser()
        result = d._deserialize_list([1, 2, 3])
        self.assertIsInstance(result, TupleRule)
        elements = result.elements
        self.assertEqual(len(elements), 3)
        for elem in elements:
            self.assertIsInstance(elem, ExprTermRule)

    def test_list_elements_followed_by_commas(self):
        d = _deser()
        result = d._deserialize_list([1, 2])
        # Structure: LSQB, ExprTermRule, COMMA, ExprTermRule, COMMA, RSQB
        comma_count = sum(1 for c in result.children if isinstance(c, COMMA))  # type: ignore[misc]
        self.assertEqual(comma_count, 2)

    def test_dict_without_block_marker_to_object(self):
        d = _deser()
        result = d._deserialize_object({"a": 1, "b": 2})
        self.assertIsInstance(result, ObjectRule)
        self.assertEqual(len(result.elements), 2)

    def test_object_elements_trailing_comma_default(self):
        d = _deser()
        result = d._deserialize_object({"a": 1})
        comma_count = sum(1 for c in result.children if isinstance(c, COMMA))  # type: ignore[misc]
        self.assertEqual(comma_count, 1)

    def test_object_elements_trailing_comma_false(self):
        opts = DeserializerOptions(object_elements_trailing_comma=False)
        d = _deser(opts)
        result = d._deserialize_object({"a": 1})
        comma_count = sum(1 for c in result.children if isinstance(c, COMMA))  # type: ignore[misc]
        self.assertEqual(comma_count, 0)

    def test_object_elements_colon_separator(self):
        opts = DeserializerOptions(object_elements_colon=True)
        d = _deser(opts)
        result = d._deserialize_object({"a": 1})
        elem = result.elements[0]
        self.assertIsInstance(elem.children[1], COLON)

    def test_object_elements_eq_separator_default(self):
        d = _deser()
        result = d._deserialize_object({"a": 1})
        elem = result.elements[0]
        self.assertIsInstance(elem.children[1], EQ)

    def test_dotted_key_object_element(self):
        d = _deser()
        result = d._deserialize_object_elem("a.b", 1)
        self.assertIsInstance(result, ObjectElemRule)
        key_rule = result.key
        self.assertIsInstance(key_rule.value, IdentifierRule)
        self.assertEqual(key_rule.value.token.value, "a.b")

    def test_expression_key_object_element(self):
        d = _deser()
        result = d._deserialize_object_elem("${(var.key)}", 1)
        self.assertIsInstance(result, ObjectElemRule)
        key_rule = result.key
        self.assertIsInstance(key_rule.value, ObjectElemKeyExpressionRule)

    def test_bare_expression_key_object_element(self):
        d = _deser()
        result = d._deserialize_object_elem("${1 + 1}", 1)
        self.assertIsInstance(result, ObjectElemRule)
        key_rule = result.key
        self.assertIsInstance(key_rule.value, ObjectElemKeyExpressionRule)

    def test_object_elem_value_is_expr_term(self):
        d = _deser()
        result = d._deserialize_object_elem("key", 42)
        self.assertIsInstance(result.children[2], ExprTermRule)

    def test_empty_list_to_empty_tuple(self):
        d = _deser()
        result = d._deserialize_list([])
        self.assertIsInstance(result, TupleRule)
        self.assertEqual(len(result.elements), 0)

    def test_empty_dict_to_empty_object(self):
        d = _deser()
        result = d._deserialize_object({})
        self.assertIsInstance(result, ObjectRule)
        self.assertEqual(len(result.elements), 0)

    def test_nested_list_in_object(self):
        d = _deser()
        result = d._deserialize_object({"items": [1, 2]})
        self.assertIsInstance(result, ObjectRule)
        elem = result.elements[0]
        expr = elem.children[2]
        self.assertIsInstance(expr, ExprTermRule)

    def test_nested_object_in_list(self):
        d = _deser()
        result = d._deserialize_list([{"a": 1}])
        self.assertIsInstance(result, TupleRule)
        self.assertEqual(len(result.elements), 1)


# --- block detection ---


class TestBlockDetection(TestCase):
    def test_is_block_with_direct_marker(self):
        d = _deser()
        val = [{IS_BLOCK: True, "x": 1}]
        self.assertTrue(d._is_block(val))

    def test_is_block_nested_dict_marker(self):
        d = _deser()
        val = [{"inner": {IS_BLOCK: True}}]
        self.assertTrue(d._is_block(val))

    def test_is_block_nested_list_dict_marker(self):
        d = _deser()
        val = [{"inner": [{IS_BLOCK: True}]}]
        self.assertTrue(d._is_block(val))

    def test_is_block_empty_list(self):
        d = _deser()
        self.assertFalse(d._is_block([]))

    def test_is_block_plain_values(self):
        d = _deser()
        self.assertFalse(d._is_block([1, 2, 3]))

    def test_is_block_non_list(self):
        d = _deser()
        self.assertFalse(d._is_block("not a list"))

    def test_contains_block_marker_direct(self):
        d = _deser()
        self.assertTrue(d._contains_block_marker({IS_BLOCK: True}))

    def test_contains_block_marker_nested(self):
        d = _deser()
        self.assertTrue(d._contains_block_marker({"a": {IS_BLOCK: True}}))

    def test_contains_block_marker_deeply_nested(self):
        d = _deser()
        self.assertTrue(d._contains_block_marker({"a": {"b": {IS_BLOCK: True}}}))

    def test_contains_block_marker_false(self):
        d = _deser()
        self.assertFalse(d._contains_block_marker({"a": 1, "b": 2}))

    def test_is_reserved_key_is_block(self):
        d = _deser()
        self.assertTrue(d._is_reserved_key(IS_BLOCK))

    def test_is_reserved_key_comments(self):
        d = _deser()
        self.assertTrue(d._is_reserved_key(COMMENTS_KEY))

    def test_is_reserved_key_normal_key(self):
        d = _deser()
        self.assertFalse(d._is_reserved_key("name"))


# --- _deserialize dispatch ---


class TestDeserializeDispatch(TestCase):
    def test_dict_with_block_marker_returns_body(self):
        d = _deser()
        result = d._deserialize({IS_BLOCK: True, "x": 1})
        self.assertIsInstance(result, BodyRule)

    def test_dict_without_block_marker_returns_object(self):
        d = _deser()
        result = d._deserialize({"a": 1})
        self.assertIsInstance(result, ObjectRule)

    def test_list_returns_tuple(self):
        d = _deser()
        result = d._deserialize([1, 2])
        self.assertIsInstance(result, TupleRule)

    def test_scalar_returns_text(self):
        d = _deser()
        result = d._deserialize(42)
        self.assertIsInstance(result, IntLitRule)


# --- _is_expression ---


class TestIsExpression(TestCase):
    def test_valid_expression(self):
        d = _deser()
        self.assertTrue(d._is_expression("${var.x}"))

    def test_not_expression_no_prefix(self):
        d = _deser()
        self.assertFalse(d._is_expression("var.x}"))

    def test_not_expression_no_suffix(self):
        d = _deser()
        self.assertFalse(d._is_expression("${var.x"))

    def test_not_expression_non_string(self):
        d = _deser()
        self.assertFalse(d._is_expression(42))

    def test_escaped_interpolation_not_expression(self):
        d = _deser()
        self.assertFalse(d._is_expression("$${literal}"))


# --- block elements deserialization ---


class TestDeserializeBlockElements(TestCase):
    def test_skips_reserved_keys(self):
        d = _deser()
        data = {"name": "test", IS_BLOCK: True}
        children = d._deserialize_block_elements(data)
        # Only "name" should produce an attribute; IS_BLOCK is skipped
        self.assertEqual(len(children), 1)
        self.assertIsInstance(children[0], AttributeRule)

    def test_block_values_produce_block_rules(self):
        d = _deser()
        data = {
            "resource": [{IS_BLOCK: True, "x": 1}],
        }
        children = d._deserialize_block_elements(data)
        self.assertEqual(len(children), 1)
        self.assertIsInstance(children[0], BlockRule)

    def test_multiple_blocks_same_key(self):
        d = _deser()
        data = {
            "resource": [
                {IS_BLOCK: True, "x": 1},
                {IS_BLOCK: True, "y": 2},
            ],
        }
        children = d._deserialize_block_elements(data)
        self.assertEqual(len(children), 2)
        self.assertIsInstance(children[0], BlockRule)
        self.assertIsInstance(children[1], BlockRule)

    def test_mixed_attributes_and_blocks(self):
        d = _deser()
        data = {
            "version": "1.0",
            "resource": [{IS_BLOCK: True}],
        }
        children = d._deserialize_block_elements(data)
        types = [type(c) for c in children]
        self.assertIn(AttributeRule, types)
        self.assertIn(BlockRule, types)
