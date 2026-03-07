# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.formatter import BaseFormatter, FormatterOptions
from hcl2.rules.base import (
    StartRule,
    BodyRule,
    BlockRule,
    AttributeRule,
)
from hcl2.rules.containers import (
    ObjectRule,
    ObjectElemRule,
    ObjectElemKeyRule,
    TupleRule,
)
from hcl2.rules.expressions import ExprTermRule
from hcl2.rules.for_expressions import (
    ForIntroRule,
    ForCondRule,
    ForTupleExprRule,
    ForObjectExprRule,
)
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.tokens import (
    NAME,
    EQ,
    LBRACE,
    RBRACE,
    LSQB,
    RSQB,
    COMMA,
    COLON,
    FOR,
    IN,
    IF,
    ELLIPSIS,
    FOR_OBJECT_ARROW,
)
from hcl2.rules.whitespace import NewLineOrCommentRule


# --- helpers ---


def _fmt(options=None):
    return BaseFormatter(options)


def _make_identifier(name):
    return IdentifierRule([NAME(name)])


def _make_expr_term(child):
    """Wrap a rule in ExprTermRule."""
    return ExprTermRule([child])


def _make_attribute(name, value_str="val"):
    """Build a simple attribute: name = value_str (identifier)."""
    return AttributeRule(
        [
            _make_identifier(name),
            EQ(),
            _make_expr_term(_make_identifier(value_str)),
        ]
    )


def _make_block(labels, body_children=None):
    body = BodyRule(body_children or [])
    children = list(labels) + [LBRACE(), body, RBRACE()]
    return BlockRule(children)


def _make_object_elem(key_name, value_name, separator=None):
    sep = separator or EQ()
    key = ObjectElemKeyRule([_make_identifier(key_name)])
    val = ExprTermRule([_make_identifier(value_name)])
    return ObjectElemRule([key, sep, val])


def _make_object(elems, trailing_commas=True):
    children = [LBRACE()]
    for elem in elems:
        children.append(elem)
        if trailing_commas:
            children.append(COMMA())
    children.append(RBRACE())
    return ObjectRule(children)


def _make_tuple(elements, trailing_commas=True):
    children = [LSQB()]
    for elem in elements:
        children.append(elem)
        if trailing_commas:
            children.append(COMMA())
    children.append(RSQB())
    return TupleRule(children)


def _nlc_value(rule):
    """Extract the string value from a NewLineOrCommentRule."""
    return rule.token.value


# --- FormatterOptions tests ---


class TestFormatterOptions(TestCase):
    def test_defaults(self):
        opts = FormatterOptions()
        self.assertEqual(opts.indent_length, 2)
        self.assertTrue(opts.open_empty_blocks)
        self.assertTrue(opts.open_empty_objects)
        self.assertFalse(opts.open_empty_tuples)
        self.assertTrue(opts.vertically_align_attributes)
        self.assertTrue(opts.vertically_align_object_elements)


# --- _build_newline ---


class TestBuildNewline(TestCase):
    def test_indent_level_zero(self):
        f = _fmt()
        nl = f._build_newline(0)
        self.assertIsInstance(nl, NewLineOrCommentRule)
        self.assertEqual(_nlc_value(nl), "\n")

    def test_indent_level_one_default_length(self):
        f = _fmt()  # indent_length=2
        nl = f._build_newline(1)
        self.assertEqual(_nlc_value(nl), "\n  ")

    def test_indent_level_two_default_length(self):
        f = _fmt()
        nl = f._build_newline(2)
        self.assertEqual(_nlc_value(nl), "\n    ")

    def test_count_two(self):
        f = _fmt()
        nl = f._build_newline(1, count=2)
        self.assertEqual(_nlc_value(nl), "\n\n  ")

    def test_custom_indent_length(self):
        opts = FormatterOptions(indent_length=4)
        f = _fmt(opts)
        nl = f._build_newline(1)
        self.assertEqual(_nlc_value(nl), "\n    ")

    def test_custom_indent_level_two(self):
        opts = FormatterOptions(indent_length=4)
        f = _fmt(opts)
        nl = f._build_newline(2)
        self.assertEqual(_nlc_value(nl), "\n        ")

    def test_tracks_last_newline(self):
        f = _fmt()
        nl1 = f._build_newline(0)
        self.assertIs(f._last_new_line, nl1)
        nl2 = f._build_newline(1)
        self.assertIs(f._last_new_line, nl2)


# --- _deindent_last_line ---


class TestDeindentLastLine(TestCase):
    def test_removes_one_indent_level(self):
        f = _fmt()  # indent_length=2
        f._build_newline(2)  # "\n    "
        f._deindent_last_line()
        self.assertEqual(f._last_new_line.token.value, "\n  ")

    def test_deindent_twice(self):
        f = _fmt()
        f._build_newline(2)  # "\n    "
        f._deindent_last_line(times=2)
        self.assertEqual(f._last_new_line.token.value, "\n")

    def test_noop_when_no_trailing_spaces(self):
        f = _fmt()
        f._build_newline(0)  # "\n"
        f._deindent_last_line()
        # Should not change since there are no trailing spaces
        self.assertEqual(f._last_new_line.token.value, "\n")


# --- format_body_rule ---


class TestFormatBodyRule(TestCase):
    def test_empty_body_no_children(self):
        f = _fmt()
        body = BodyRule([])
        # Body with no parent (not inside StartRule) — leading newline is
        # added then immediately popped since there are no real children.
        f.format_body_rule(body, 0)
        self.assertEqual(len(body._children), 0)

    def test_body_with_single_attribute(self):
        f = _fmt()
        attr = _make_attribute("name")
        body = BodyRule([attr])
        # Need a parent so it's not in StartRule context
        block = _make_block([_make_identifier("test")])
        block._children[-2] = body  # replace the empty body
        body._parent = block

        f.format_body_rule(body, 1)
        # Should have: newline, attr, (final newline removed by pop)
        nlc_children = [
            c for c in body._children if isinstance(c, NewLineOrCommentRule)
        ]
        self.assertGreaterEqual(len(nlc_children), 1)
        # The attribute should still be in children
        attr_children = [c for c in body._children if isinstance(c, AttributeRule)]
        self.assertEqual(len(attr_children), 1)

    def test_body_inside_start_no_leading_newline(self):
        f = _fmt()
        attr = _make_attribute("name")
        body = BodyRule([attr])
        _start = StartRule([body])
        f.format_body_rule(body, 0)
        # First child should be the attribute, not a newline (since in_start=True)
        self.assertIsInstance(body._children[0], AttributeRule)

    def test_body_with_attribute_and_block(self):
        f = _fmt()
        attr = _make_attribute("version")
        inner_block = _make_block([_make_identifier("provider")])
        body = BodyRule([attr, inner_block])
        _start = StartRule([body])

        f.format_body_rule(body, 0)
        # Should contain attr, block, and various newlines
        attr_count = sum(1 for c in body._children if isinstance(c, AttributeRule))
        block_count = sum(1 for c in body._children if isinstance(c, BlockRule))
        self.assertEqual(attr_count, 1)
        self.assertEqual(block_count, 1)


# --- format_block_rule ---


class TestFormatBlockRule(TestCase):
    def test_nonempty_block_closing_newline(self):
        f = _fmt()
        block = _make_block(
            [_make_identifier("resource")],
            [_make_attribute("name")],
        )
        _start = StartRule([BodyRule([block])])
        f.format_block_rule(block, indent_level=1)
        # Last child should be RBRACE; second-to-last should be a newline
        self.assertIsInstance(block.children[-1], RBRACE)
        self.assertIsInstance(block.children[-2], NewLineOrCommentRule)

    def test_empty_block_open_true(self):
        opts = FormatterOptions(open_empty_blocks=True)
        f = _fmt(opts)
        block = _make_block([_make_identifier("resource")])
        _start = StartRule([BodyRule([block])])

        f.format_block_rule(block, indent_level=1)
        # Should insert a double-newline before RBRACE
        nlc_before_rbrace = block.children[-2]
        self.assertIsInstance(nlc_before_rbrace, NewLineOrCommentRule)
        # count=2 means two newlines
        self.assertTrue(_nlc_value(nlc_before_rbrace).startswith("\n\n"))

    def test_empty_block_open_false(self):
        opts = FormatterOptions(open_empty_blocks=False)
        f = _fmt(opts)
        block = _make_block([_make_identifier("resource")])
        _start = StartRule([BodyRule([block])])

        f.format_block_rule(block, indent_level=1)
        # Should NOT insert newline before RBRACE
        nlc_children = [
            c for c in block.children if isinstance(c, NewLineOrCommentRule)
        ]
        # Only the body formatting newlines, but no double-newline insertion
        has_double_nl = any(_nlc_value(c).startswith("\n\n") for c in nlc_children)
        self.assertFalse(has_double_nl)


# --- format_tuple_rule ---


class TestFormatTupleRule(TestCase):
    def test_nonempty_tuple_newlines(self):
        f = _fmt()
        elem1 = _make_expr_term(_make_identifier("a"))
        elem2 = _make_expr_term(_make_identifier("b"))
        tup = _make_tuple([elem1, elem2])

        f.format_tuple_rule(tup, indent_level=1)
        # Should have newlines after LSQB and after each COMMA
        nlc_count = sum(1 for c in tup._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreaterEqual(nlc_count, 2)

    def test_empty_tuple_default_no_newlines(self):
        f = _fmt()  # open_empty_tuples=False by default
        tup = _make_tuple([], trailing_commas=False)

        original_len = len(tup.children)
        f.format_tuple_rule(tup, indent_level=1)
        # No newlines should be inserted
        self.assertEqual(len(tup.children), original_len)

    def test_empty_tuple_open_true(self):
        opts = FormatterOptions(open_empty_tuples=True)
        f = _fmt(opts)
        tup = _make_tuple([], trailing_commas=False)

        f.format_tuple_rule(tup, indent_level=1)
        # Should insert a double-newline
        nlc_children = [c for c in tup.children if isinstance(c, NewLineOrCommentRule)]
        self.assertEqual(len(nlc_children), 1)
        self.assertTrue(_nlc_value(nlc_children[0]).startswith("\n\n"))

    def test_deindent_on_last_line(self):
        f = _fmt()
        elem = _make_expr_term(_make_identifier("a"))
        tup = _make_tuple([elem])

        f.format_tuple_rule(tup, indent_level=1)
        # The last newline should have been deindented
        last_nlc = f._last_new_line
        # At indent_level=1 with length 2, deindented means "\n" (no spaces)
        self.assertEqual(_nlc_value(last_nlc), "\n")


# --- format_object_rule ---


class TestFormatObjectRule(TestCase):
    def test_nonempty_object_newlines(self):
        f = _fmt()
        elem = _make_object_elem("key", "val")
        obj = _make_object([elem])

        f.format_object_rule(obj, indent_level=1)
        nlc_count = sum(1 for c in obj._children if isinstance(c, NewLineOrCommentRule))
        # Should have newlines after LBRACE, after elements, before RBRACE
        self.assertGreaterEqual(nlc_count, 2)

    def test_empty_object_open_true(self):
        opts = FormatterOptions(open_empty_objects=True)
        f = _fmt(opts)
        obj = _make_object([], trailing_commas=False)

        f.format_object_rule(obj, indent_level=1)
        nlc_children = [c for c in obj.children if isinstance(c, NewLineOrCommentRule)]
        self.assertEqual(len(nlc_children), 1)
        self.assertTrue(_nlc_value(nlc_children[0]).startswith("\n\n"))

    def test_empty_object_open_false(self):
        opts = FormatterOptions(open_empty_objects=False)
        f = _fmt(opts)
        obj = _make_object([], trailing_commas=False)

        original_len = len(obj.children)
        f.format_object_rule(obj, indent_level=1)
        self.assertEqual(len(obj.children), original_len)

    def test_deindent_last_line(self):
        f = _fmt()
        elem = _make_object_elem("key", "val")
        obj = _make_object([elem])

        f.format_object_rule(obj, indent_level=1)
        last_nlc = f._last_new_line
        self.assertEqual(_nlc_value(last_nlc), "\n")

    def test_multiple_elements_get_newlines_between(self):
        f = _fmt()
        elem1 = _make_object_elem("a", "x")
        elem2 = _make_object_elem("b", "y")
        obj = _make_object([elem1, elem2], trailing_commas=False)

        f.format_object_rule(obj, indent_level=1)
        # Should have newlines between the elements
        nlc_count = sum(1 for c in obj._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreaterEqual(
            nlc_count, 3
        )  # after LBRACE, between elems, before RBRACE


# --- format_expression dispatch ---


class TestFormatExpression(TestCase):
    def test_object_delegates(self):
        f = _fmt()
        elem = _make_object_elem("key", "val")
        obj = _make_object([elem])
        expr = _make_expr_term(obj)

        f.format_expression(expr, indent_level=1)
        # Object should have been formatted (newlines inserted)
        nlc_count = sum(1 for c in obj._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreater(nlc_count, 0)

    def test_tuple_delegates(self):
        f = _fmt()
        inner = _make_expr_term(_make_identifier("a"))
        tup = _make_tuple([inner])
        expr = _make_expr_term(tup)

        f.format_expression(expr, indent_level=1)
        nlc_count = sum(1 for c in tup._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreater(nlc_count, 0)

    def test_nested_expr_term_recursive(self):
        f = _fmt()
        obj = _make_object([_make_object_elem("k", "v")])
        inner_expr = _make_expr_term(obj)
        outer_expr = _make_expr_term(inner_expr)

        f.format_expression(outer_expr, indent_level=1)
        nlc_count = sum(1 for c in obj._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreater(nlc_count, 0)


# --- vertical alignment ---


class TestVerticalAlignment(TestCase):
    def test_align_attributes_pads_eq(self):
        f = _fmt()
        attr_short = _make_attribute("a", "x")
        attr_long = _make_attribute("long_name", "y")
        body = BodyRule([attr_short, attr_long])

        f._vertically_align_attributes_in_body(body)
        # "a" has length 1, "long_name" has length 9, diff is 8
        eq_short = attr_short.children[1]
        eq_long = attr_long.children[1]
        self.assertEqual(len(eq_short.value) - len(eq_long.value), 8)

    def test_non_attribute_breaks_sequence(self):
        f = _fmt()
        attr1 = _make_attribute("x", "a")
        block = _make_block([_make_identifier("blk")])
        attr2 = _make_attribute("yy", "b")
        body = BodyRule([attr1, block, attr2])

        f._vertically_align_attributes_in_body(body)
        # attr1 is in its own group (length 1), attr2 in its own group (length 2)
        # No cross-group padding: each group aligns independently
        eq1 = attr1.children[1]
        eq2 = attr2.children[1]
        # Both should have no extra padding (single-element groups)
        self.assertEqual(eq1.value.strip(), "=")
        self.assertEqual(eq2.value.strip(), "=")

    def test_align_object_elems_pads_separator(self):
        f = _fmt()
        elem_short = _make_object_elem("a", "x")
        elem_long = _make_object_elem("long_key", "y")
        obj = _make_object([elem_short, elem_long], trailing_commas=False)

        f._vertically_align_object_elems(obj)
        sep_short = elem_short.children[1]
        sep_long = elem_long.children[1]
        # "a" serializes to length 1, "long_key" to length 8, diff is 7
        self.assertGreater(len(sep_short.value), len(sep_long.value))

    def test_colon_separator_extra_space(self):
        f = _fmt()
        elem = _make_object_elem("key", "val", separator=COLON())
        obj = _make_object([elem], trailing_commas=False)

        f._vertically_align_object_elems(obj)
        sep = elem.children[1]
        # Single element: spaces_to_add=0, but COLON gets +1
        self.assertTrue(sep.value.endswith(":"))
        self.assertEqual(sep.value, " :")


# --- indent_length customization ---


class TestIndentLength(TestCase):
    def test_indent_length_4(self):
        opts = FormatterOptions(indent_length=4)
        f = _fmt(opts)
        nl = f._build_newline(1)
        self.assertEqual(_nlc_value(nl), "\n    ")

    def test_indent_length_4_level_2(self):
        opts = FormatterOptions(indent_length=4)
        f = _fmt(opts)
        nl = f._build_newline(2)
        self.assertEqual(_nlc_value(nl), "\n        ")

    def test_deindent_with_indent_length_4(self):
        opts = FormatterOptions(indent_length=4)
        f = _fmt(opts)
        f._build_newline(2)  # "\n        "
        f._deindent_last_line()
        self.assertEqual(f._last_new_line.token.value, "\n    ")

    def test_format_body_uses_indent_length(self):
        opts = FormatterOptions(indent_length=4)
        f = _fmt(opts)
        attr = _make_attribute("name")
        body = BodyRule([attr])
        block = _make_block([_make_identifier("test")])
        block._children[-2] = body
        body._parent = block

        f.format_body_rule(body, 1)
        nlc_children = [
            c for c in body._children if isinstance(c, NewLineOrCommentRule)
        ]
        # At least one newline should have 4 spaces of indent
        has_4_space = any("    " in _nlc_value(c) for c in nlc_children)
        self.assertTrue(has_4_space)


# --- format_tree entry point ---


class TestFormatTree(TestCase):
    def test_format_tree_with_start_rule(self):
        f = _fmt()
        attr = _make_attribute("key")
        body = BodyRule([attr])
        start = StartRule([body])

        f.format_tree(start)
        # Should have processed the body (attribute is first child since in_start)
        self.assertIsInstance(body._children[0], AttributeRule)

    def test_format_tree_with_non_start_rule_noop(self):
        f = _fmt()
        body = BodyRule([])
        # Passing a non-StartRule should be a no-op
        f.format_tree(body)
        self.assertEqual(len(body._children), 0)

    def test_full_format_start_with_block(self):
        f = _fmt()
        attr = _make_attribute("ami", "abc")
        block = _make_block(
            [_make_identifier("resource")],
            [attr],
        )
        body = BodyRule([block])
        start = StartRule([body])

        f.format_tree(start)
        # Block should have a closing newline before RBRACE
        self.assertIsInstance(block.children[-1], RBRACE)
        self.assertIsInstance(block.children[-2], NewLineOrCommentRule)


# --- for-expression helpers ---


def _make_for_intro(iterable_name="items", iterator_name="item"):
    """Build a simple for_intro: for iterator_name in iterable_name :"""
    return ForIntroRule(
        [
            FOR(),
            _make_identifier(iterator_name),
            IN(),
            _make_expr_term(_make_identifier(iterable_name)),
            COLON(),
        ]
    )


def _make_for_cond(condition_name="cond"):
    """Build a for_cond: if condition_name"""
    return ForCondRule(
        [
            IF(),
            _make_expr_term(_make_identifier(condition_name)),
        ]
    )


def _make_for_tuple_expr(value_name="val", condition=None):
    """Build a for_tuple_expr: [for item in items : value_name]"""
    children = [
        LSQB(),
        _make_for_intro(),
        _make_expr_term(_make_identifier(value_name)),
    ]
    if condition is not None:
        children.append(condition)
    children.append(RSQB())
    return ForTupleExprRule(children)


def _make_for_object_expr(key_name="k", value_name="v", ellipsis=False, condition=None):
    """Build a for_object_expr: {for item in items : key_name => value_name}"""
    children = [
        LBRACE(),
        _make_for_intro(),
        _make_expr_term(_make_identifier(key_name)),
        FOR_OBJECT_ARROW(),
        _make_expr_term(_make_identifier(value_name)),
    ]
    if ellipsis:
        children.append(ELLIPSIS())
    if condition is not None:
        children.append(condition)
    children.append(RBRACE())
    return ForObjectExprRule(children)


# --- format_fortupleexpr ---


class TestFormatForTupleExpr(TestCase):
    def test_basic_no_condition_no_spurious_newline(self):
        """No condition → index 5 should be None, no spurious blank line."""
        f = _fmt()
        expr = _make_for_tuple_expr()
        f.format_fortupleexpr(expr, indent_level=1)

        self.assertIsNone(expr.children[5])
        for idx in [1, 3, 7]:
            self.assertIsInstance(expr.children[idx], NewLineOrCommentRule)

    def test_basic_no_condition_deindents_closing(self):
        """Last newline (before ]) should be deindented."""
        f = _fmt()
        expr = _make_for_tuple_expr()
        f.format_fortupleexpr(expr, indent_level=1)

        last_nl = expr.children[7]
        self.assertEqual(_nlc_value(last_nl), "\n")

    def test_with_condition_newline_before_if(self):
        """With condition → index 5 should be a newline before `if`."""
        f = _fmt()
        cond = _make_for_cond()
        expr = _make_for_tuple_expr(condition=cond)
        f.format_fortupleexpr(expr, indent_level=1)

        self.assertIsInstance(expr.children[5], NewLineOrCommentRule)
        for idx in [1, 3, 7]:
            self.assertIsInstance(expr.children[idx], NewLineOrCommentRule)

    def test_with_condition_deindents_closing(self):
        """Even with condition, last newline (before ]) is deindented."""
        f = _fmt()
        cond = _make_for_cond()
        expr = _make_for_tuple_expr(condition=cond)
        f.format_fortupleexpr(expr, indent_level=1)

        last_nl = expr.children[7]
        self.assertEqual(_nlc_value(last_nl), "\n")

    def test_nested_value_object_formatting(self):
        """Value expression containing an object should be formatted recursively."""
        f = _fmt()
        obj = _make_object([_make_object_elem("k", "v")])
        children = [
            LSQB(),
            _make_for_intro(),
            _make_expr_term(obj),
            RSQB(),
        ]
        expr = ForTupleExprRule(children)

        f.format_fortupleexpr(expr, indent_level=1)

        nlc_count = sum(1 for c in obj._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreater(nlc_count, 0)

    def test_for_intro_iterable_formatting(self):
        """ForIntroRule's iterable expression should be formatted recursively."""
        f = _fmt()
        obj = _make_object([_make_object_elem("k", "v")])
        intro = ForIntroRule(
            [
                FOR(),
                _make_identifier("item"),
                IN(),
                _make_expr_term(obj),
                COLON(),
            ]
        )
        children = [LSQB(), intro, _make_expr_term(_make_identifier("val")), RSQB()]
        expr = ForTupleExprRule(children)

        f.format_fortupleexpr(expr, indent_level=1)

        nlc_count = sum(1 for c in obj._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreater(nlc_count, 0)


# --- format_forobjectexpr ---


class TestFormatForObjectExpr(TestCase):
    def test_basic_no_condition_no_ellipsis(self):
        """No condition, no ellipsis → indices 6, 8, 10 should be None."""
        f = _fmt()
        expr = _make_for_object_expr()
        f.format_forobjectexpr(expr, indent_level=1)

        self.assertIsNone(expr.children[6])
        self.assertIsNone(expr.children[8])
        self.assertIsNone(expr.children[10])
        for idx in [1, 3, 12]:
            self.assertIsInstance(expr.children[idx], NewLineOrCommentRule)

    def test_basic_deindents_closing(self):
        """Last newline (before }) should be deindented."""
        f = _fmt()
        expr = _make_for_object_expr()
        f.format_forobjectexpr(expr, indent_level=1)

        last_nl = expr.children[12]
        self.assertEqual(_nlc_value(last_nl), "\n")

    def test_with_condition_newline_before_if(self):
        """With condition → index 10 should be a newline before `if`."""
        f = _fmt()
        cond = _make_for_cond()
        expr = _make_for_object_expr(condition=cond)
        f.format_forobjectexpr(expr, indent_level=1)

        self.assertIsInstance(expr.children[10], NewLineOrCommentRule)
        self.assertIsNone(expr.children[6])
        self.assertIsNone(expr.children[8])

    def test_with_condition_deindents_closing(self):
        """Even with condition, last newline (before }) is deindented."""
        f = _fmt()
        cond = _make_for_cond()
        expr = _make_for_object_expr(condition=cond)
        f.format_forobjectexpr(expr, indent_level=1)

        last_nl = expr.children[12]
        self.assertEqual(_nlc_value(last_nl), "\n")

    def test_with_ellipsis_and_condition(self):
        """With ellipsis and condition → index 10 is newline, 6/8 cleared."""
        f = _fmt()
        cond = _make_for_cond()
        expr = _make_for_object_expr(ellipsis=True, condition=cond)
        f.format_forobjectexpr(expr, indent_level=1)

        self.assertIsInstance(expr.children[9], ELLIPSIS)
        self.assertIsInstance(expr.children[10], NewLineOrCommentRule)
        self.assertIsNone(expr.children[6])
        self.assertIsNone(expr.children[8])

    def test_nested_value_tuple_formatting(self):
        """Value expression containing a tuple should be formatted recursively."""
        f = _fmt()
        inner_tup = _make_tuple([_make_expr_term(_make_identifier("a"))])
        children = [
            LBRACE(),
            _make_for_intro(),
            _make_expr_term(_make_identifier("k")),
            FOR_OBJECT_ARROW(),
            _make_expr_term(inner_tup),
            RBRACE(),
        ]
        expr = ForObjectExprRule(children)

        f.format_forobjectexpr(expr, indent_level=1)

        nlc_count = sum(
            1 for c in inner_tup._children if isinstance(c, NewLineOrCommentRule)
        )
        self.assertGreater(nlc_count, 0)

    def test_for_cond_expression_formatting(self):
        """ForCondRule's condition expression should be formatted recursively."""
        f = _fmt()
        obj = _make_object([_make_object_elem("k", "v")])
        cond = ForCondRule([IF(), _make_expr_term(obj)])
        expr = _make_for_object_expr(condition=cond)

        f.format_forobjectexpr(expr, indent_level=1)

        nlc_count = sum(1 for c in obj._children if isinstance(c, NewLineOrCommentRule))
        self.assertGreater(nlc_count, 0)
