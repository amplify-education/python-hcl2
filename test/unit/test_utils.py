# pylint: disable=C0103,C0114,C0115,C0116
import dataclasses
from unittest import TestCase

from hcl2.utils import (
    SerializationContext,
    SerializationOptions,
    is_dollar_string,
    process_escape_sequences,
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

    def test_replace_multiple_fields(self):
        ctx = SerializationContext()
        both = ctx.replace(inside_dollar_string=True, inside_parentheses=True)
        self.assertTrue(both.inside_dollar_string)
        self.assertTrue(both.inside_parentheses)
        self.assertFalse(ctx.inside_dollar_string)
        self.assertFalse(ctx.inside_parentheses)

    def test_a_field_cannot_be_assigned(self):
        """The point of the type: a caller's context cannot be changed under it.

        A traversal descends by building a child, so nothing writes back. An
        assignment that used to be a temporary mutation is now an error at the
        point it is written rather than a value another thread can observe.
        """
        ctx = SerializationContext()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ctx.inside_dollar_string = True  # type: ignore[misc]
        self.assertFalse(ctx.inside_dollar_string)

    def test_it_is_hashable_now_that_it_is_frozen(self):
        ctx = SerializationContext()
        self.assertEqual(len({ctx, SerializationContext()}), 1)
        self.assertEqual(len({ctx, ctx.replace(inside_parentheses=True)}), 2)


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


class TestProcessEscapeSequences(TestCase):
    """Escape resolution used by `strip_string_quotes`."""

    def test_no_backslash_is_returned_unchanged(self):
        self.assertEqual(process_escape_sequences("plain text"), "plain text")

    def test_simple_escapes(self):
        self.assertEqual(process_escape_sequences(r"a\nb\tc\rd"), "a\nb\tc\rd")

    def test_escaped_quote(self):
        self.assertEqual(process_escape_sequences(r"say \"hi\""), 'say "hi"')

    def test_escaped_backslash(self):
        self.assertEqual(process_escape_sequences(r"back\\slash"), "back\\slash")

    def test_escaped_backslash_is_not_reused_by_the_next_character(self):
        r"""A single pass: `\\n` cannot become a newline."""
        self.assertEqual(process_escape_sequences(r"back\\nslash"), "back\\nslash")

    def test_unicode_escape(self):
        self.assertEqual(process_escape_sequences(r"café"), "café")

    def test_long_unicode_escape(self):
        self.assertEqual(process_escape_sequences(r"\U0001F600"), "\U0001f600")

    def test_malformed_unicode_escape_is_preserved(self):
        self.assertEqual(process_escape_sequences(r"\u12"), r"\u12")

    def test_non_hex_unicode_escape_is_preserved(self):
        self.assertEqual(process_escape_sequences(r"\uZZZZ"), r"\uZZZZ")

    def test_unknown_escape_is_preserved(self):
        self.assertEqual(process_escape_sequences(r"keep \q intact"), r"keep \q intact")

    def test_trailing_backslash_is_preserved(self):
        self.assertEqual(process_escape_sequences("trailing\\"), "trailing\\")

    def test_highest_valid_codepoint_is_decoded(self):
        self.assertEqual(process_escape_sequences(r"\U0010FFFF"), "\U0010ffff")

    def test_codepoint_past_the_unicode_maximum_is_preserved(self):
        """`chr` raises above 0x10FFFF; the escape is left verbatim instead."""
        self.assertEqual(process_escape_sequences(r"\U00110000"), r"\U00110000")

    def test_codepoint_too_large_for_c_int_is_preserved(self):
        """`int(digits, 16)` fits in a Python int but overflows `chr`."""
        self.assertEqual(process_escape_sequences(r"\UFFFFFFFF"), r"\UFFFFFFFF")

    def test_lone_surrogate_is_preserved(self):
        r"""`chr(0xD800)` succeeds but the result cannot be encoded to UTF-8."""
        self.assertEqual(process_escape_sequences(r"\uD800"), r"\uD800")
        self.assertEqual(process_escape_sequences(r"\uDFFF"), r"\uDFFF")

    def test_characters_bracketing_the_surrogate_range_still_decode(self):
        """Only D800-DFFF is rejected; the codepoints either side still decode."""
        self.assertEqual(process_escape_sequences(r"\uD7FF"), "\ud7ff")
        self.assertEqual(process_escape_sequences(r"\uE000"), "\ue000")

    def test_result_is_always_utf8_encodable(self):
        """The point of rejecting surrogates: callers can safely write the value out."""
        for source in (r"\uD800", r"\uDFFF", r"\U00110000", r"\UFFFFFFFF"):
            with self.subTest(source=source):
                process_escape_sequences(source).encode("utf-8")
