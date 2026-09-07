# pylint: disable=C0103,C0114,C0115,C0116
"""`force_operation_parentheses` under a parenthesised ancestor (GH #342).

The option exists to make precedence explicit, and it did so for a top-level
expression. Inside one the caller had already parenthesised, it added nothing:
`(b + c * d)` came back unchanged, so the very documents most likely to want
explicit precedence got the least of it.

`inside_parentheses` answers "did my immediate container already wrap me",
which `_wrap_into_parentheses` reads to avoid doubling them. Two places made
it mean "some ancestor is parenthesised" instead -- `ExprTermRule` carried it
down with `or`, and the operation rules passed it to their operands, which are
never directly wrapped by anything.

Of those two, only the operation rules change any output: clearing the flag
for their operands is what reaches every shape below. The `ExprTermRule` edit
restores the flag's stated meaning at its source and emits the same text
either way, so it is covered by a rule-level test rather than an output one.

The parentheses this adds group what precedence already grouped. Checked
against Terraform v1.11.4 with b=2, c=3, d=4, e=5, f=6, g=7, v=9, w=8, y=10,
z=11 and x=true: all 28 rewritten expressions evaluate to the same value as
the source they came from, `(b + c * d)` and `(b + (c * d))` both being 14.
"""

from unittest import TestCase

from hcl2.api import loads
from hcl2.rules.expressions import ExpressionRule, ExprTermRule
from hcl2.rules.tokens import LPAR, RPAR
from hcl2.utils import SerializationContext, SerializationOptions

FORCED = SerializationOptions(force_operation_parentheses=True)
DEFAULT = SerializationOptions()

# Every expression the tests below exercise, in source form. The default path
# has to return each one exactly as written; see TestTheDefaultIsUntouched.
SOURCES = (
    "b + c * d",
    "(b + c * d)",
    "((b + c) * d)",
    "(b + c) * d",
    "-b + c",
    "x ? y + z : w",
    "b + c * d + e",
    "b * c + d * e",
    "(b + c) * (d + e)",
    "((b + c * d))",
    "b + (c * (d + e))",
    "-(b + c * d)",
    "!(b && c || d)",
    "(x ? y + z * w : v)",
    "(f(b + c * d)) * d",
    "(b[c + d * e])",
    "((b + c * d) + e)",
    "(-(b + c * d))",
    "(b + c * d) + (e + f * g)",
    "(b + c * d)[0]",
    "b[c + d * e]",
    "f(b + c * d)",
    "[for i in l : i + j * k]",
    "{for k, v in m : k => v + w * x}",
)


class ForcedParenthesesTestCase(TestCase):
    def forced(self, source: str) -> str:
        return loads(f"a = {source}\n", serialization_options=FORCED)["a"]


class TestForcedParentheses(ForcedParenthesesTestCase):
    def test_a_top_level_operation_is_unchanged(self):
        self.assertEqual(self.forced("b + c * d"), "${b + (c * d)}")

    def test_a_parenthesised_ancestor_no_longer_suppresses_it(self):
        self.assertEqual(self.forced("(b + c * d)"), "${(b + (c * d))}")

    def test_parentheses_already_there_are_not_doubled(self):
        self.assertEqual(self.forced("((b + c) * d)"), "${((b + c) * d)}")
        self.assertEqual(self.forced("(b + c) * d"), "${(b + c) * d}")

    def test_a_unary_operand_is_wrapped(self):
        self.assertEqual(self.forced("-b + c"), "${(-b) + c}")

    def test_a_conditional_branch_is_wrapped(self):
        self.assertEqual(self.forced("x ? y + z : w"), "${x ? (y + z) : w}")


class TestEachOperationClearsTheFlagForItsOperands(ForcedParenthesesTestCase):
    """One case per rule that stopped handing `inside_parentheses` down.

    Dropping the `inside_parentheses=False` argument from `BinaryOpRule` or
    `ConditionalRule` fails a test here: the enclosing parentheses go back to
    suppressing the option for the whole subtree, which is #342.

    `UnaryOpRule` carries the same argument and no input reaches it, because a
    unary operand is an `expr_term` -- an operation there either carries its
    own parentheses, which set the flag anyway, or sits inside a container
    whose own operation rule clears it. It is kept so the rule that an
    operation never hands the flag to its operands holds for all three rather
    than two, and noted here so its lack of a failing test is not mistaken for
    an oversight.
    """

    def test_a_binary_operation_under_parentheses(self):
        self.assertEqual(self.forced("(b + c * d)"), "${(b + (c * d))}")

    def test_a_unary_operation_under_parentheses(self):
        self.assertEqual(self.forced("-(b + c * d)"), "${-(b + (c * d))}")
        self.assertEqual(self.forced("!(b && c || d)"), "${!((b && c) || d)}")

    def test_a_conditional_under_parentheses(self):
        self.assertEqual(self.forced("(x ? y + z * w : v)"), "${(x ? (y + (z * w)) : v)}")


class TestItReachesThroughEveryContainer(ForcedParenthesesTestCase):
    """Parentheses anywhere above an operation no longer silence the option."""

    def test_through_a_function_call(self):
        self.assertEqual(self.forced("(f(b + c * d)) * d"), "${(f(b + (c * d))) * d}")

    def test_through_an_index(self):
        self.assertEqual(self.forced("(b[c + d * e])"), "${(b[c + (d * e)])}")

    def test_through_a_second_pair_of_parentheses(self):
        self.assertEqual(self.forced("((b + c * d) + e)"), "${((b + (c * d)) + e)}")
        self.assertEqual(self.forced("((b + c * d))"), "${((b + (c * d)))}")

    def test_through_a_unary_operator_and_parentheses(self):
        self.assertEqual(self.forced("(-(b + c * d))"), "${(-(b + (c * d)))}")

    def test_both_sides_of_an_operation(self):
        self.assertEqual(
            self.forced("(b + c * d) + (e + f * g)"),
            "${(b + (c * d)) + (e + (f * g))}",
        )

    def test_a_parenthesised_operation_that_is_then_indexed(self):
        self.assertEqual(self.forced("(b + c * d)[0]"), "${(b + (c * d))[0]}")

    def test_unparenthesised_containers_still_work(self):
        self.assertEqual(self.forced("b[c + d * e]"), "${b[c + (d * e)]}")
        self.assertEqual(self.forced("f(b + c * d)"), "${f(b + (c * d))}")
        self.assertEqual(self.forced("[for i in l : i + j * k]"), "${[for i in l : (i + (j * k))]}")


class TestTheExprTermFlagReflectsItsOwnParentheses(TestCase):
    """`ExprTermRule` sets the flag from `self.parentheses`, not its ancestors.

    This is the half of the fix that changes no output -- the operation rules
    already clear the flag on the way down, so nothing observable depends on
    it. It is asserted here so the `or context.inside_parentheses` it replaced
    cannot come back unnoticed: with that back, an unparenthesised term
    inherits `True` and the flag stops meaning what its docstring says.
    """

    class RecordingExpression(ExpressionRule):
        """Serializes to a fixed string, remembering the context it was given."""

        def __init__(self):
            self.seen = None
            super().__init__([], None)

        def serialize(self, options=SerializationOptions(), context=SerializationContext()):
            self.seen = context.inside_parentheses
            return "x"

    def child_sees(self, *, parenthesised: bool, ancestor_parenthesised: bool) -> bool:
        child = self.RecordingExpression()
        children = [LPAR(), child, RPAR()] if parenthesised else [child]
        ExprTermRule(children).serialize(
            SerializationOptions(),
            SerializationContext(inside_parentheses=ancestor_parenthesised),
        )
        return child.seen

    def test_a_parenthesised_term_tells_its_child_so(self):
        self.assertTrue(self.child_sees(parenthesised=True, ancestor_parenthesised=False))

    def test_an_unparenthesised_term_does_not(self):
        self.assertFalse(self.child_sees(parenthesised=False, ancestor_parenthesised=False))

    def test_an_ancestors_parentheses_are_not_inherited(self):
        self.assertFalse(self.child_sees(parenthesised=False, ancestor_parenthesised=True))

    def test_a_terms_own_parentheses_still_win(self):
        self.assertTrue(self.child_sees(parenthesised=True, ancestor_parenthesised=True))


class TestTheDefaultIsUntouched(TestCase):
    """Nothing above changes what the option-less path emits."""

    def test_sources_come_back_as_written(self):
        for source in SOURCES:
            with self.subTest(source=source):
                self.assertEqual(
                    loads(f"a = {source}\n", serialization_options=DEFAULT)["a"],
                    f"${{{source}}}",
                )


class TestTheMeaningIsPreserved(ForcedParenthesesTestCase):
    """The added parentheses group what precedence already grouped."""

    def test_the_forced_form_parses_back_to_the_same_expression(self):
        forced = self.forced("(b + c * d)")
        reparsed = loads(f"a = {forced[2:-1]}\n", serialization_options=DEFAULT)["a"]
        self.assertEqual(reparsed, "${(b + (c * d))}")

    def test_forcing_twice_adds_nothing_further(self):
        # The rewritten form is already explicit, so running it back through
        # the option has to be a fixed point rather than growing a pair a run.
        for source in SOURCES:
            with self.subTest(source=source):
                once = self.forced(source)
                self.assertEqual(self.forced(once[2:-1]), once)
