# pylint: disable=C0103,C0114,C0115,C0116,C0302
"""Unit tests for hcl2.reconstructor."""

from unittest import TestCase

from lark import Tree, Token

from hcl2.reconstructor import HCLReconstructor
from hcl2.rules.base import BlockRule, AttributeRule, BodyRule, StartRule
from hcl2.rules.containers import (
    ObjectRule,
    ObjectElemRule,
    ObjectElemKeyRule,
    TupleRule,
)
from hcl2.rules.expressions import (
    BinaryTermRule,
    ExprTermRule,
    ConditionalRule,
    UnaryOpRule,
    BinaryOpRule,
)
from hcl2.rules.for_expressions import (
    ForIntroRule,
    ForCondRule,
    ForTupleExprRule,
    ForObjectExprRule,
)
from hcl2.rules.literal_rules import BinaryOperatorRule, IdentifierRule
from hcl2.rules.strings import StringRule
from hcl2.rules.tokens import (
    NAME,
    NL_OR_COMMENT,
    EQ,
    LBRACE,
    RBRACE,
    LSQB,
    RSQB,
    COMMA,
    COLON,
    QMARK,
    FOR,
    IN,
    IF,
    ELLIPSIS,
    FOR_OBJECT_ARROW,
    DBLQUOTE,
    STRING_CHARS,
    BINARY_OP,
)
from hcl2.rules.whitespace import NewLineOrCommentRule


# --- helpers ---


def _r():
    """Create a fresh HCLReconstructor."""
    return HCLReconstructor()


def _make_identifier(name):
    return IdentifierRule([NAME(name)])


def _make_expr_term(child):
    return ExprTermRule([child])


def _make_nlc(value):
    """Build a NewLineOrCommentRule with the given string value."""
    return NewLineOrCommentRule([NL_OR_COMMENT(value)])


def _make_attribute(name, value_str="val"):
    return AttributeRule(
        [
            _make_identifier(name),
            EQ(),
            _make_expr_term(_make_identifier(value_str)),
        ]
    )


def _make_string(text):
    return StringRule([DBLQUOTE(), STRING_CHARS(text), DBLQUOTE()])


def _make_block(type_name, labels=None, body_children=None):
    body = BodyRule(body_children or [])
    children = [_make_identifier(type_name)]
    for label in labels or []:
        children.append(label)
    children += [LBRACE(), body, RBRACE()]
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


def _to_lark(rule):
    """Convert a LarkElement tree to a Lark Tree for the reconstructor."""
    return rule.to_lark()


def _reconstruct(rule, postproc=None):
    """Helper: convert rule to Lark tree and reconstruct to string."""
    r = _r()
    return r.reconstruct(_to_lark(rule), postproc=postproc)


# --- HCLReconstructor basic behavior ---


class TestReconstructorResetState(TestCase):
    def test_reset_clears_all_state(self):
        r = _r()
        r._last_was_space = False
        r._current_indent = 3
        r._last_token_name = "NAME"
        r._last_rule_name = "identifier"
        r._reset_state()
        self.assertTrue(r._last_was_space)
        self.assertEqual(r._current_indent, 0)
        self.assertIsNone(r._last_token_name)
        self.assertIsNone(r._last_rule_name)

    def test_reconstruct_resets_state_each_call(self):
        r = _r()
        tree1 = Tree(
            "start",
            [Tree("body", [Token("NAME", "a"), Token("EQ", "="), Token("NAME", "b")])],
        )
        tree2 = Tree("start", [Tree("body", [Token("NAME", "x")])])
        r.reconstruct(tree1)
        result = r.reconstruct(tree2)
        # Second call should not be affected by state from first
        self.assertEqual(result, "x\n")


class TestReconstructorTrailingNewline(TestCase):
    def test_result_ends_with_newline(self):
        tree = Tree("start", [Tree("body", [Token("NAME", "x")])])
        r = _r()
        result = r.reconstruct(tree)
        self.assertTrue(result.endswith("\n"))

    def test_empty_body_returns_empty_string(self):
        tree = Tree("start", [Tree("body", [])])
        r = _r()
        result = r.reconstruct(tree)
        self.assertEqual(result, "")

    def test_already_has_newline_not_doubled(self):
        tree = Tree("start", [Tree("body", [Token("NL_OR_COMMENT", "\n")])])
        r = _r()
        result = r.reconstruct(tree)
        self.assertEqual(result, "\n")


class TestReconstructorPostproc(TestCase):
    def test_postproc_applied(self):
        tree = Tree("start", [Tree("body", [Token("NAME", "hello")])])
        r = _r()
        result = r.reconstruct(tree, postproc=lambda s: s.upper())
        self.assertEqual(result, "HELLO\n")

    def test_postproc_none_is_noop(self):
        tree = Tree("start", [Tree("body", [Token("NAME", "hello")])])
        r = _r()
        result = r.reconstruct(tree)
        self.assertEqual(result, "hello\n")


# --- Space insertion: tokens ---


class TestSpaceBeforeToken(TestCase):
    def test_no_space_at_beginning(self):
        """First token should not get a leading space."""
        r = _r()
        token = Token("NAME", "x")
        self.assertFalse(r._should_add_space_before(token))

    def test_no_space_when_last_was_space(self):
        r = _r()
        r._last_was_space = True
        r._last_token_name = "NAME"
        token = Token("NAME", "y")
        self.assertFalse(r._should_add_space_before(token))

    def test_space_before_lbrace_in_block(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("LBRACE", "{")
        self.assertTrue(
            r._should_add_space_before(token, parent_rule_name=BlockRule.lark_name())
        )

    def test_no_space_before_lbrace_outside_block(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("LBRACE", "{")
        self.assertFalse(r._should_add_space_before(token, parent_rule_name="object"))

    def test_no_space_default_for_unmatched_token(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "LPAR"
        self.assertFalse(r._should_add_space_before(Token("RBRACE", "}"), None))


class TestSpaceAroundEq(TestCase):
    def test_space_before_eq(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("EQ", "=")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_after_eq(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "EQ"
        token = Token("NAME", "value")
        self.assertTrue(r._should_add_space_before(token))


class TestSpaceAroundBinaryOps(TestCase):
    def test_space_before_binary_op(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        for op in [
            "PLUS",
            "MINUS",
            "ASTERISK",
            "SLASH",
            "DOUBLE_EQ",
            "NEQ",
            "LT",
            "GT",
            "LEQ",
            "GEQ",
            "PERCENT",
            "DOUBLE_AMP",
            "DOUBLE_PIPE",
        ]:
            token = Token(op, "+")
            self.assertTrue(
                r._should_add_space_before(token),
                f"Expected space before {op}",
            )

    def test_space_after_binary_op(self):
        r = _r()
        r._last_was_space = False
        for op in ["PLUS", "MINUS", "DOUBLE_EQ"]:
            r._last_token_name = op
            token = Token("NAME", "x")
            self.assertTrue(
                r._should_add_space_before(token),
                f"Expected space after {op}",
            )

    def test_no_space_in_unary_op(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "MINUS"
        token = Token("NAME", "x")
        self.assertFalse(
            r._should_add_space_before(token, parent_rule_name=UnaryOpRule.lark_name())
        )


class TestSpaceAroundConditional(TestCase):
    def test_space_before_qmark(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("QMARK", "?")
        self.assertTrue(
            r._should_add_space_before(
                token, parent_rule_name=ConditionalRule.lark_name()
            )
        )

    def test_space_before_colon(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("COLON", ":")
        self.assertTrue(
            r._should_add_space_before(
                token, parent_rule_name=ConditionalRule.lark_name()
            )
        )

    def test_space_after_qmark(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "QMARK"
        token = Token("NAME", "x")
        self.assertTrue(
            r._should_add_space_before(
                token, parent_rule_name=ConditionalRule.lark_name()
            )
        )

    def test_space_after_colon(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COLON"
        token = Token("NAME", "x")
        self.assertTrue(
            r._should_add_space_before(
                token, parent_rule_name=ConditionalRule.lark_name()
            )
        )

    def test_no_space_qmark_outside_conditional(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        self.assertFalse(r._should_add_space_before(Token("QMARK", "?"), None))


class TestSpaceAroundComma(TestCase):
    def test_space_after_comma_before_name(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COMMA"
        token = Token("NAME", "x")
        self.assertTrue(r._should_add_space_before(token))

    def test_no_space_after_comma_before_rsqb(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COMMA"
        token = Token("RSQB", "]")
        self.assertFalse(r._should_add_space_before(token))

    def test_no_space_after_comma_before_nl(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COMMA"
        token = Token("NL_OR_COMMENT", "\n")
        self.assertFalse(r._should_add_space_before(token))


class TestSpaceAroundForKeywords(TestCase):
    def test_space_before_for(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "LSQB"
        token = Token("FOR", "for")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_before_in(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("IN", "in")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_before_if(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("IF", "if")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_after_for(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "FOR"
        token = Token("NAME", "x")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_after_in(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "IN"
        token = Token("NAME", "items")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_after_if(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "IF"
        token = Token("NAME", "cond")
        self.assertTrue(r._should_add_space_before(token))

    def test_no_space_after_for_before_nl(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "FOR"
        token = Token("NL_OR_COMMENT", "\n")
        self.assertFalse(r._should_add_space_before(token))

    def test_no_space_after_in_before_nl(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "IN"
        self.assertFalse(r._should_add_space_before(Token("NL_OR_COMMENT", "\n")))

    def test_no_space_after_if_before_nl(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "IF"
        self.assertFalse(r._should_add_space_before(Token("NL_OR_COMMENT", "\n")))


class TestSpaceAroundForObjectArrow(TestCase):
    def test_space_before_arrow(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("FOR_OBJECT_ARROW", "=>")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_after_arrow(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "FOR_OBJECT_ARROW"
        token = Token("NAME", "v")
        self.assertTrue(r._should_add_space_before(token))


class TestSpaceAroundEllipsis(TestCase):
    def test_space_before_ellipsis(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("ELLIPSIS", "...")
        self.assertTrue(r._should_add_space_before(token))

    def test_space_after_ellipsis(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "ELLIPSIS"
        token = Token("NAME", "x")
        self.assertTrue(r._should_add_space_before(token))


class TestSpaceColonInForIntro(TestCase):
    def test_space_before_colon_in_for_intro(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("COLON", ":")
        self.assertTrue(
            r._should_add_space_before(token, parent_rule_name=ForIntroRule.lark_name())
        )

    def test_no_space_colon_outside_for_intro_and_conditional(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "LPAR"
        self.assertFalse(r._should_add_space_before(Token("COLON", ":"), None))


# --- Space insertion: tree nodes ---


class TestSpaceBeforeTree(TestCase):
    def test_space_between_labels_in_block(self):
        """Space between identifier labels within a block."""
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        r._last_rule_name = IdentifierRule.lark_name()
        tree = Tree(IdentifierRule.lark_name(), [Token("NAME", "label2")])
        self.assertTrue(
            r._should_add_space_before(tree, parent_rule_name=BlockRule.lark_name())
        )

    def test_space_between_string_and_identifier_in_block(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "DBLQUOTE"
        r._last_rule_name = StringRule.lark_name()
        tree = Tree(IdentifierRule.lark_name(), [Token("NAME", "label")])
        self.assertTrue(
            r._should_add_space_before(tree, parent_rule_name=BlockRule.lark_name())
        )

    def test_no_space_between_labels_outside_block(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        r._last_rule_name = IdentifierRule.lark_name()
        tree = Tree(IdentifierRule.lark_name(), [Token("NAME", "x")])
        self.assertFalse(r._should_add_space_before(tree, parent_rule_name="attribute"))

    def test_no_space_for_non_label_tree_in_block(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        r._last_rule_name = StringRule.lark_name()
        self.assertFalse(
            r._should_add_space_before(
                Tree("expr_term", []), parent_rule_name=BlockRule.lark_name()
            )
        )

    def test_space_after_qmark_before_tree_in_conditional(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "QMARK"
        tree = Tree("expr_term", [Token("NAME", "x")])
        self.assertTrue(
            r._should_add_space_before(
                tree, parent_rule_name=ConditionalRule.lark_name()
            )
        )

    def test_space_after_colon_before_tree_in_conditional(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COLON"
        tree = Tree("expr_term", [Token("NAME", "x")])
        self.assertTrue(
            r._should_add_space_before(
                tree, parent_rule_name=ConditionalRule.lark_name()
            )
        )

    def test_no_space_after_other_token_before_tree_in_conditional(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "LPAR"
        self.assertFalse(
            r._should_add_space_before(
                Tree("expr_term", []), parent_rule_name=ConditionalRule.lark_name()
            )
        )

    def test_space_after_colon_before_tree_in_for_tuple_expr(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COLON"
        tree = Tree("expr_term", [Token("NAME", "x")])
        self.assertTrue(
            r._should_add_space_before(
                tree, parent_rule_name=ForTupleExprRule.lark_name()
            )
        )

    def test_space_after_colon_before_tree_in_for_object_expr(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COLON"
        tree = Tree("expr_term", [Token("NAME", "x")])
        self.assertTrue(
            r._should_add_space_before(
                tree, parent_rule_name=ForObjectExprRule.lark_name()
            )
        )

    def test_no_space_after_colon_before_nlc_in_for_expr(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COLON"
        tree = Tree("new_line_or_comment", [Token("NL_OR_COMMENT", "\n")])
        self.assertFalse(
            r._should_add_space_before(
                tree, parent_rule_name=ForTupleExprRule.lark_name()
            )
        )

    def test_no_space_after_colon_outside_for_expr(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "COLON"
        self.assertFalse(r._should_add_space_before(Tree("expr_term", []), None))

    def test_no_space_default_for_unmatched_tree(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "LPAR"
        self.assertFalse(r._should_add_space_before(Tree("body", []), None))


# --- _reconstruct_token ---


class TestReconstructToken(TestCase):
    def test_simple_token(self):
        r = _r()
        token = Token("NAME", "hello")
        result = r._reconstruct_token(token)
        self.assertEqual(result, "hello")

    def test_updates_last_token_name(self):
        r = _r()
        token = Token("NAME", "hello")
        r._reconstruct_token(token)
        self.assertEqual(r._last_token_name, "NAME")

    def test_updates_last_was_space_for_newline(self):
        r = _r()
        token = Token("NL_OR_COMMENT", "\n")
        r._reconstruct_token(token)
        self.assertTrue(r._last_was_space)

    def test_updates_last_was_space_trailing_space(self):
        r = _r()
        r._reconstruct_token(Token("NAME", "x "))
        self.assertTrue(r._last_was_space)

    def test_updates_last_was_space_false(self):
        r = _r()
        token = Token("NAME", "hello")
        r._reconstruct_token(token)
        self.assertFalse(r._last_was_space)

    def test_space_prepended_when_needed(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        token = Token("EQ", "=")
        result = r._reconstruct_token(token)
        self.assertEqual(result, " =")

    def test_empty_token_skips_last_was_space_update(self):
        r = _r()
        initial = r._last_was_space
        r._reconstruct_token(Token("NAME", ""))
        self.assertEqual(r._last_was_space, initial)


# --- _reconstruct_node ---


class TestReconstructNode(TestCase):
    def test_token_returns_list_of_one(self):
        r = _r()
        token = Token("NAME", "x")
        result = r._reconstruct_node(token)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "x")

    def test_tree_returns_list(self):
        r = _r()
        tree = Tree("identifier", [Token("NAME", "x")])
        result = r._reconstruct_node(tree)
        self.assertIsInstance(result, list)
        self.assertEqual("".join(result), "x")

    def test_fallback_non_tree_non_token(self):
        r = _r()
        result = r._reconstruct_node(42)
        self.assertEqual(result, ["42"])


# --- _reconstruct_tree ---


class TestReconstructTree(TestCase):
    def test_simple_tree(self):
        r = _r()
        tree = Tree("identifier", [Token("NAME", "myvar")])
        result = r._reconstruct_tree(tree)
        self.assertEqual("".join(result), "myvar")

    def test_updates_last_rule_name(self):
        r = _r()
        tree = Tree("identifier", [Token("NAME", "x")])
        r._reconstruct_tree(tree)
        self.assertEqual(r._last_rule_name, "identifier")

    def test_nested_tree(self):
        r = _r()
        inner = Tree("identifier", [Token("NAME", "x")])
        outer = Tree("expr_term", [inner])
        result = r._reconstruct_tree(outer)
        self.assertEqual("".join(result), "x")

    def test_unary_op_no_space_between_op_and_operand(self):
        r = _r()
        tree = Tree(
            UnaryOpRule.lark_name(),
            [
                Token("MINUS", "-"),
                Tree("expr_term", [Token("NAME", "x")]),
            ],
        )
        result = r._reconstruct_tree(tree)
        self.assertEqual("".join(result), "-x")

    def test_empty_tree_returns_empty_list(self):
        r = _r()
        tree = Tree("body", [])
        result = r._reconstruct_tree(tree)
        self.assertEqual(result, [])

    def test_updates_last_was_space_for_trailing_newline(self):
        r = _r()
        tree = Tree("new_line_or_comment", [Token("NL_OR_COMMENT", "\n")])
        r._reconstruct_tree(tree)
        self.assertTrue(r._last_was_space)

    def test_updates_last_was_space_for_trailing_non_space(self):
        r = _r()
        tree = Tree("identifier", [Token("NAME", "x")])
        r._reconstruct_tree(tree)
        self.assertFalse(r._last_was_space)

    def test_tree_prepends_space_for_block_labels(self):
        r = _r()
        r._last_was_space = False
        r._last_token_name = "NAME"
        r._last_rule_name = IdentifierRule.lark_name()
        tree = Tree(IdentifierRule.lark_name(), [Token("NAME", "b")])
        result = r._reconstruct_tree(tree, parent_rule_name=BlockRule.lark_name())
        text = "".join(result)
        self.assertEqual(text, " b")


# --- End-to-end reconstruction via LarkElement.to_lark() ---


class TestReconstructAttribute(TestCase):
    def test_simple_attribute(self):
        attr = _make_attribute("name", "value")
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertEqual(result, "name = value\n")


class TestReconstructBlock(TestCase):
    def test_empty_block(self):
        block = _make_block("resource")
        body = BodyRule([block])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertEqual(result, "resource {}\n")

    def test_block_with_string_label(self):
        block = _make_block("resource", labels=[_make_string("aws_instance")])
        body = BodyRule([block])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn('resource "aws_instance"', result)
        self.assertIn("{}", result)

    def test_block_with_identifier_labels(self):
        block = _make_block(
            "resource",
            labels=[_make_identifier("aws_instance"), _make_string("example")],
        )
        body = BodyRule([block])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("resource", result)
        self.assertIn("aws_instance", result)
        self.assertIn('"example"', result)

    def test_block_with_body(self):
        attr = _make_attribute("ami", "abc")
        nlc = _make_nlc("\n  ")
        nlc2 = _make_nlc("\n")
        block = _make_block("resource", body_children=[nlc, attr, nlc2])
        body = BodyRule([block])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("resource {", result)
        self.assertIn("ami = abc", result)
        self.assertIn("}", result)


class TestReconstructConditional(TestCase):
    def test_conditional_expression(self):
        # condition ? true_val : false_val
        cond = ConditionalRule(
            [
                _make_expr_term(_make_identifier("enabled")),
                QMARK(),
                _make_expr_term(_make_identifier("yes")),
                COLON(),
                _make_expr_term(_make_identifier("no")),
            ]
        )
        attr = AttributeRule([_make_identifier("result"), EQ(), _make_expr_term(cond)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("enabled ? yes : no", result)


class TestReconstructUnaryOp(TestCase):
    def test_negation(self):
        unary = UnaryOpRule(
            [
                BinaryOperatorRule([BINARY_OP("-")]),
                _make_expr_term(_make_identifier("x")),
            ]
        )
        attr = AttributeRule([_make_identifier("val"), EQ(), _make_expr_term(unary)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("-x", result)
        # Should NOT have a space between - and x
        self.assertNotIn("- x", result)


class TestReconstructBinaryOp(TestCase):
    def test_addition_raw_lark_tree(self):
        """Test binary op spacing using raw Lark tokens (as the parser produces)."""
        r = _r()
        # Raw Lark tree with PLUS token type (as the Lark parser produces)
        tree = Tree(
            "start",
            [
                Tree(
                    "body",
                    [
                        Tree(
                            "attribute",
                            [
                                Tree("identifier", [Token("NAME", "sum")]),
                                Token("EQ", "="),
                                Tree(
                                    "binary_op",
                                    [
                                        Tree(
                                            "expr_term",
                                            [
                                                Tree(
                                                    "identifier", [Token("NAME", "a")]
                                                ),
                                            ],
                                        ),
                                        Tree(
                                            "binary_term",
                                            [
                                                Tree(
                                                    "binary_operator",
                                                    [Token("PLUS", "+")],
                                                ),
                                                Tree(
                                                    "expr_term",
                                                    [
                                                        Tree(
                                                            "identifier",
                                                            [Token("NAME", "b")],
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                        Tree(
                                            "new_line_or_comment",
                                            [Token("NL_OR_COMMENT", "\n")],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        result = r.reconstruct(tree)
        self.assertIn("a + b", result)

    def test_addition_via_to_lark(self):
        """Test binary op via LarkElement.to_lark() produces valid output."""
        binary = BinaryOpRule(
            [
                _make_expr_term(_make_identifier("a")),
                BinaryTermRule(
                    [
                        BinaryOperatorRule([BINARY_OP("+")]),
                        _make_expr_term(_make_identifier("b")),
                    ]
                ),
                _make_nlc("\n"),
            ]
        )
        attr = AttributeRule([_make_identifier("sum"), EQ(), _make_expr_term(binary)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("sum", result)
        self.assertIn("a", result)
        self.assertIn("+", result)
        self.assertIn("b", result)


class TestReconstructForTupleExpr(TestCase):
    def test_basic_for_tuple(self):
        intro = ForIntroRule(
            [
                FOR(),
                _make_identifier("item"),
                IN(),
                _make_expr_term(_make_identifier("items")),
                COLON(),
            ]
        )
        expr = ForTupleExprRule(
            [
                LSQB(),
                intro,
                _make_expr_term(_make_identifier("item")),
                RSQB(),
            ]
        )
        attr = AttributeRule([_make_identifier("result"), EQ(), _make_expr_term(expr)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("for item in items :", result)
        self.assertIn("item", result)
        self.assertIn("[", result)
        self.assertIn("]", result)

    def test_for_tuple_with_condition(self):
        intro = ForIntroRule(
            [
                FOR(),
                _make_identifier("item"),
                IN(),
                _make_expr_term(_make_identifier("items")),
                COLON(),
            ]
        )
        cond = ForCondRule([IF(), _make_expr_term(_make_identifier("item"))])
        expr = ForTupleExprRule(
            [
                LSQB(),
                intro,
                _make_expr_term(_make_identifier("item")),
                cond,
                RSQB(),
            ]
        )
        attr = AttributeRule([_make_identifier("result"), EQ(), _make_expr_term(expr)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("if item", result)


class TestReconstructForObjectExpr(TestCase):
    def test_basic_for_object(self):
        intro = ForIntroRule(
            [
                FOR(),
                _make_identifier("k"),
                COMMA(),
                _make_identifier("v"),
                IN(),
                _make_expr_term(_make_identifier("items")),
                COLON(),
            ]
        )
        expr = ForObjectExprRule(
            [
                LBRACE(),
                intro,
                _make_expr_term(_make_identifier("k")),
                FOR_OBJECT_ARROW(),
                _make_expr_term(_make_identifier("v")),
                RBRACE(),
            ]
        )
        attr = AttributeRule([_make_identifier("result"), EQ(), _make_expr_term(expr)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("for k, v in items :", result)
        self.assertIn("k => v", result)

    def test_for_object_with_ellipsis(self):
        intro = ForIntroRule(
            [
                FOR(),
                _make_identifier("k"),
                IN(),
                _make_expr_term(_make_identifier("items")),
                COLON(),
            ]
        )
        expr = ForObjectExprRule(
            [
                LBRACE(),
                intro,
                _make_expr_term(_make_identifier("k")),
                FOR_OBJECT_ARROW(),
                _make_expr_term(_make_identifier("v")),
                ELLIPSIS(),
                RBRACE(),
            ]
        )
        attr = AttributeRule([_make_identifier("result"), EQ(), _make_expr_term(expr)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("...", result)


class TestReconstructTuple(TestCase):
    def test_inline_tuple(self):
        tup = _make_tuple(
            [
                _make_expr_term(_make_identifier("a")),
                _make_expr_term(_make_identifier("b")),
            ]
        )
        attr = AttributeRule([_make_identifier("list"), EQ(), _make_expr_term(tup)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("[a, b,]", result)


class TestReconstructObject(TestCase):
    def test_inline_object(self):
        obj = _make_object(
            [_make_object_elem("key", "val")],
        )
        attr = AttributeRule([_make_identifier("obj"), EQ(), _make_expr_term(obj)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("key = val,", result)
        self.assertIn("{", result)
        self.assertIn("}", result)


class TestReconstructMultipleAttributes(TestCase):
    def test_two_attributes_with_newlines(self):
        attr1 = _make_attribute("a", "1")
        attr2 = _make_attribute("b", "2")
        nlc = _make_nlc("\n")
        body = BodyRule([attr1, nlc, attr2])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn("a = 1", result)
        self.assertIn("b = 2", result)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 2)


class TestReconstructString(TestCase):
    def test_quoted_string(self):
        s = _make_string("hello world")
        attr = AttributeRule([_make_identifier("greeting"), EQ(), _make_expr_term(s)])
        body = BodyRule([attr])
        start = StartRule([body])
        result = _reconstruct(start)
        self.assertIn('"hello world"', result)
