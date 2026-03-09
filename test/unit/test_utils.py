# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.utils import (
    SerializationOptions,
    SerializationContext,
    is_dollar_string,
    to_dollar_string,
    unwrap_dollar_string,
    wrap_into_parentheses,
)


class TestSerializationOptions(TestCase):
    def test_default_values(self):
        opts = SerializationOptions()
        self.assertTrue(opts.with_comments)
        self.assertFalse(opts.with_meta)
        self.assertFalse(opts.wrap_objects)
        self.assertFalse(opts.wrap_tuples)
        self.assertTrue(opts.explicit_blocks)
        self.assertTrue(opts.preserve_heredocs)
        self.assertFalse(opts.force_operation_parentheses)

    def test_custom_values(self):
        opts = SerializationOptions(
            with_comments=False,
            with_meta=True,
            force_operation_parentheses=True,
        )
        self.assertFalse(opts.with_comments)
        self.assertTrue(opts.with_meta)
        self.assertTrue(opts.force_operation_parentheses)


class TestSerializationContext(TestCase):
    def test_default_values(self):
        ctx = SerializationContext()
        self.assertFalse(ctx.inside_dollar_string)
        self.assertFalse(ctx.inside_parentheses)

    def test_replace_returns_new_instance(self):
        ctx = SerializationContext()
        new_ctx = ctx.replace(inside_dollar_string=True)
        self.assertIsNot(ctx, new_ctx)
        self.assertFalse(ctx.inside_dollar_string)
        self.assertTrue(new_ctx.inside_dollar_string)

    def test_modify_mutates_and_restores(self):
        ctx = SerializationContext()
        self.assertFalse(ctx.inside_dollar_string)

        with ctx.modify(inside_dollar_string=True):
            self.assertTrue(ctx.inside_dollar_string)

        self.assertFalse(ctx.inside_dollar_string)

    def test_modify_restores_on_exception(self):
        ctx = SerializationContext()

        with self.assertRaises(ValueError):
            with ctx.modify(inside_dollar_string=True, inside_parentheses=True):
                self.assertTrue(ctx.inside_dollar_string)
                self.assertTrue(ctx.inside_parentheses)
                raise ValueError("test")

        self.assertFalse(ctx.inside_dollar_string)
        self.assertFalse(ctx.inside_parentheses)

    def test_modify_multiple_fields(self):
        ctx = SerializationContext()
        with ctx.modify(inside_dollar_string=True, inside_parentheses=True):
            self.assertTrue(ctx.inside_dollar_string)
            self.assertTrue(ctx.inside_parentheses)
        self.assertFalse(ctx.inside_dollar_string)
        self.assertFalse(ctx.inside_parentheses)


class TestIsDollarString(TestCase):
    def test_valid_dollar_string(self):
        self.assertTrue(is_dollar_string("${x}"))

    def test_nested_dollar_string(self):
        self.assertTrue(is_dollar_string("${a + b}"))

    def test_plain_string(self):
        self.assertFalse(is_dollar_string("foo"))

    def test_incomplete_prefix(self):
        self.assertFalse(is_dollar_string("${"))

    def test_non_string_input(self):
        self.assertFalse(is_dollar_string(42))
        self.assertFalse(is_dollar_string(None))

    def test_empty_dollar_string(self):
        self.assertTrue(is_dollar_string("${}"))

    def test_dollar_without_brace(self):
        self.assertFalse(is_dollar_string("$x}"))

    def test_missing_closing_brace(self):
        self.assertFalse(is_dollar_string("${x"))


class TestToDollarString(TestCase):
    def test_wraps_plain_string(self):
        self.assertEqual(to_dollar_string("x"), "${x}")

    def test_idempotent_on_dollar_string(self):
        self.assertEqual(to_dollar_string("${x}"), "${x}")

    def test_wraps_empty(self):
        self.assertEqual(to_dollar_string(""), "${}")

    def test_wraps_expression(self):
        self.assertEqual(to_dollar_string("a + b"), "${a + b}")


class TestUnwrapDollarString(TestCase):
    def test_strips_wrapping(self):
        self.assertEqual(unwrap_dollar_string("${x}"), "x")

    def test_noop_on_plain_string(self):
        self.assertEqual(unwrap_dollar_string("foo"), "foo")

    def test_strips_complex_expression(self):
        self.assertEqual(unwrap_dollar_string("${a + b}"), "a + b")


class TestWrapIntoParentheses(TestCase):
    def test_plain_string(self):
        self.assertEqual(wrap_into_parentheses("x"), "(x)")

    def test_dollar_string(self):
        self.assertEqual(wrap_into_parentheses("${x}"), "${(x)}")

    def test_expression_string(self):
        self.assertEqual(wrap_into_parentheses("a + b"), "(a + b)")

    def test_dollar_expression(self):
        self.assertEqual(wrap_into_parentheses("${a + b}"), "${(a + b)}")
