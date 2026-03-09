# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.expressions import ExpressionRule
from hcl2.rules.strings import (
    InterpolationRule,
    StringPartRule,
    StringRule,
    HeredocTemplateRule,
    HeredocTrimTemplateRule,
)
from hcl2.rules.tokens import (
    INTERP_START,
    RBRACE,
    DBLQUOTE,
    STRING_CHARS,
    ESCAPED_INTERPOLATION,
    HEREDOC_TEMPLATE,
    HEREDOC_TRIM_TEMPLATE,
)
from hcl2.utils import SerializationOptions, SerializationContext


# --- Stubs ---


class StubExpression(ExpressionRule):
    """Minimal ExpressionRule that serializes to a fixed string."""

    def __init__(self, value):
        self._stub_value = value
        super().__init__([], None)

    def serialize(self, options=SerializationOptions(), context=SerializationContext()):
        return self._stub_value


# --- Helpers ---


def _make_string_part_chars(text):
    return StringPartRule([STRING_CHARS(text)])


def _make_string_part_escaped(text):
    return StringPartRule([ESCAPED_INTERPOLATION(text)])


def _make_string_part_interpolation(expr_value):
    interp = InterpolationRule([INTERP_START(), StubExpression(expr_value), RBRACE()])
    return StringPartRule([interp])


def _make_string(parts):
    """Build StringRule from a list of StringPartRule children."""
    return StringRule([DBLQUOTE(), *parts, DBLQUOTE()])


# --- InterpolationRule tests ---


class TestInterpolationRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(InterpolationRule.lark_name(), "interpolation")

    def test_expression_property(self):
        expr = StubExpression("var.name")
        rule = InterpolationRule([INTERP_START(), expr, RBRACE()])
        self.assertIs(rule.expression, expr)

    def test_serialize_wraps_in_dollar_string(self):
        rule = InterpolationRule([INTERP_START(), StubExpression("var.name"), RBRACE()])
        self.assertEqual(rule.serialize(), "${var.name}")

    def test_serialize_idempotent_if_already_dollar(self):
        rule = InterpolationRule([INTERP_START(), StubExpression("${x}"), RBRACE()])
        self.assertEqual(rule.serialize(), "${x}")

    def test_serialize_expression_result(self):
        rule = InterpolationRule([INTERP_START(), StubExpression("a + b"), RBRACE()])
        self.assertEqual(rule.serialize(), "${a + b}")


# --- StringPartRule tests ---


class TestStringPartRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(StringPartRule.lark_name(), "string_part")

    def test_content_property_string_chars(self):
        token = STRING_CHARS("hello")
        rule = StringPartRule([token])
        self.assertIs(rule.content, token)

    def test_serialize_string_chars(self):
        rule = _make_string_part_chars("hello world")
        self.assertEqual(rule.serialize(), "hello world")

    def test_serialize_escaped_interpolation(self):
        rule = _make_string_part_escaped("$${aws:username}")
        self.assertEqual(rule.serialize(), "$${aws:username}")

    def test_serialize_interpolation(self):
        rule = _make_string_part_interpolation("var.name")
        self.assertEqual(rule.serialize(), "${var.name}")

    def test_content_property_interpolation(self):
        interp = InterpolationRule([INTERP_START(), StubExpression("x"), RBRACE()])
        rule = StringPartRule([interp])
        self.assertIs(rule.content, interp)


# --- StringRule tests ---


class TestStringRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(StringRule.lark_name(), "string")

    def test_string_parts_property(self):
        p1 = _make_string_part_chars("hello")
        p2 = _make_string_part_chars(" world")
        rule = _make_string([p1, p2])
        self.assertEqual(rule.string_parts, [p1, p2])

    def test_string_parts_empty(self):
        rule = _make_string([])
        self.assertEqual(rule.string_parts, [])

    def test_serialize_plain_string(self):
        rule = _make_string([_make_string_part_chars("hello")])
        self.assertEqual(rule.serialize(), '"hello"')

    def test_serialize_empty_string(self):
        rule = _make_string([])
        self.assertEqual(rule.serialize(), '""')

    def test_serialize_concatenated_parts(self):
        rule = _make_string(
            [
                _make_string_part_chars("prefix:"),
                _make_string_part_interpolation("var.name"),
                _make_string_part_chars("-suffix"),
            ]
        )
        self.assertEqual(rule.serialize(), '"prefix:${var.name}-suffix"')

    def test_serialize_escaped_and_interpolation(self):
        rule = _make_string(
            [
                _make_string_part_interpolation("bar"),
                _make_string_part_escaped("$${baz:bat}"),
            ]
        )
        self.assertEqual(rule.serialize(), '"${bar}$${baz:bat}"')

    def test_serialize_only_interpolation(self):
        rule = _make_string([_make_string_part_interpolation("x")])
        self.assertEqual(rule.serialize(), '"${x}"')


# --- HeredocTemplateRule tests ---


class TestHeredocTemplateRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(HeredocTemplateRule.lark_name(), "heredoc_template")

    def test_heredoc_property(self):
        token = HEREDOC_TEMPLATE("<<EOF\nhello\nEOF")
        rule = HeredocTemplateRule([token])
        self.assertIs(rule.heredoc, token)

    def test_serialize_preserve_heredocs(self):
        token = HEREDOC_TEMPLATE("<<EOF\nhello world\nEOF")
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=True)
        result = rule.serialize(opts)
        # Preserves heredoc, strips trailing whitespace, wraps in quotes
        self.assertEqual(result, '"<<EOF\nhello world\nEOF"')

    def test_serialize_no_preserve_extracts_content(self):
        token = HEREDOC_TEMPLATE("<<EOF\nhello world\nEOF")
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"hello world"')

    def test_serialize_no_preserve_multiline(self):
        token = HEREDOC_TEMPLATE("<<EOF\nline1\nline2\nEOF")
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"line1\\nline2"')

    def test_serialize_no_preserve_escapes_quotes(self):
        token = HEREDOC_TEMPLATE('<<EOF\nsay "hello"\nEOF')
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"say \\"hello\\""')

    def test_serialize_no_preserve_escapes_backslashes(self):
        token = HEREDOC_TEMPLATE("<<EOF\npath\\to\\file\nEOF")
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"path\\\\to\\\\file"')

    def test_serialize_no_preserve_escapes_backslashes_before_quotes(self):
        token = HEREDOC_TEMPLATE('<<EOF\n\\"escaped\\"\nEOF')
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        # \ becomes \\, then " becomes \" → \\" and \\"
        self.assertEqual(result, '"\\\\\\"escaped\\\\\\""')

    def test_serialize_no_preserve_json_content(self):
        token = HEREDOC_TEMPLATE('<<EOF\n{"key": "value"}\nEOF')
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"{\\"key\\": \\"value\\"}"')

    def test_serialize_no_preserve_escapes_newlines(self):
        token = HEREDOC_TEMPLATE("<<EOF\nfirst\nsecond\nthird\nEOF")
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"first\\nsecond\\nthird"')

    def test_serialize_no_preserve_invalid_raises(self):
        token = HEREDOC_TEMPLATE("not a heredoc")
        rule = HeredocTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        with self.assertRaises(RuntimeError):
            rule.serialize(opts)


# --- HeredocTrimTemplateRule tests ---


class TestHeredocTrimTemplateRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(HeredocTrimTemplateRule.lark_name(), "heredoc_template_trim")

    def test_serialize_preserve_heredocs_trims_indent(self):
        token = HEREDOC_TRIM_TEMPLATE("<<-EOF\n    line1\n    line2\nEOF")
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=True)
        result = rule.serialize(opts)
        # Should strip 0 leading spaces (the raw value is preserved,
        # but lines are individually trimmed by min leading spaces)
        # Raw: "<<-EOF\n    line1\n    line2\nEOF" → stripped trailing → "<<-EOF\n    line1\n    line2\nEOF"
        # Lines: ["<<-EOF", "    line1", "    line2", "EOF"]
        # Min spaces: 0 (from "<<-EOF" and "EOF")
        # Result: same lines joined
        self.assertEqual(result, '"<<-EOF\n    line1\n    line2\nEOF"')

    def test_serialize_no_preserve_trims_indent(self):
        token = HEREDOC_TRIM_TEMPLATE("<<-EOF\n    line1\n    line2\nEOF")
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        # Extracted content: "    line1\n    line2"
        # Lines: ["    line1", "    line2"], min_spaces=4
        # Trimmed: ["line1", "line2"]
        self.assertEqual(result, '"line1\\nline2"')

    def test_serialize_no_preserve_mixed_indent(self):
        token = HEREDOC_TRIM_TEMPLATE("<<-EOF\n  line1\n    line2\n  line3\nEOF")
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        # Content: "  line1\n    line2\n  line3", min_spaces=2
        self.assertEqual(result, '"line1\\n  line2\\nline3"')

    def test_serialize_no_preserve_escapes_quotes(self):
        token = HEREDOC_TRIM_TEMPLATE('<<-EOF\n    say "hello"\nEOF')
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"say \\"hello\\""')

    def test_serialize_no_preserve_escapes_backslashes(self):
        token = HEREDOC_TRIM_TEMPLATE("<<-EOF\n    path\\to\\file\nEOF")
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"path\\\\to\\\\file"')

    def test_serialize_no_preserve_json_content(self):
        token = HEREDOC_TRIM_TEMPLATE('<<-EOF\n    {"key": "value"}\nEOF')
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"{\\"key\\": \\"value\\"}"')

    def test_serialize_no_preserve_escapes_newlines(self):
        token = HEREDOC_TRIM_TEMPLATE("<<-EOF\n    first\n    second\n    third\nEOF")
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        result = rule.serialize(opts)
        self.assertEqual(result, '"first\\nsecond\\nthird"')

    def test_serialize_no_preserve_invalid_raises(self):
        token = HEREDOC_TRIM_TEMPLATE("not a heredoc")
        rule = HeredocTrimTemplateRule([token])
        opts = SerializationOptions(preserve_heredocs=False)
        with self.assertRaises(RuntimeError):
            rule.serialize(opts)
