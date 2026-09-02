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
"""

from unittest import TestCase

from hcl2.api import loads
from hcl2.utils import SerializationOptions

FORCED = SerializationOptions(force_operation_parentheses=True)
DEFAULT = SerializationOptions()


class TestForcedParentheses(TestCase):
    def _forced(self, source: str) -> str:
        return loads(f"a = {source}\n", serialization_options=FORCED)["a"]

    def test_a_top_level_operation_is_unchanged(self):
        self.assertEqual(self._forced("b + c * d"), "${b + (c * d)}")

    def test_a_parenthesised_ancestor_no_longer_suppresses_it(self):
        self.assertEqual(self._forced("(b + c * d)"), "${(b + (c * d))}")

    def test_parentheses_already_there_are_not_doubled(self):
        self.assertEqual(self._forced("((b + c) * d)"), "${((b + c) * d)}")
        self.assertEqual(self._forced("(b + c) * d"), "${(b + c) * d}")

    def test_a_unary_operand_is_wrapped(self):
        self.assertEqual(self._forced("-b + c"), "${(-b) + c}")

    def test_a_conditional_branch_is_wrapped(self):
        self.assertEqual(self._forced("x ? y + z : w"), "${x ? (y + z) : w}")


class TestTheDefaultIsUntouched(TestCase):
    """Nothing above changes what the option-less path emits."""

    def test_sources_come_back_as_written(self):
        for source in (
            "b + c * d",
            "(b + c * d)",
            "((b + c) * d)",
            "(b + c) * d",
            "-b + c",
            "x ? y + z : w",
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    loads(f"a = {source}\n", serialization_options=DEFAULT)["a"],
                    f"${{{source}}}",
                )


class TestTheMeaningIsPreserved(TestCase):
    """The added parentheses group what precedence already grouped.

    Checked with OpenTofu v1.12.5: with b=2, c=3, d=4, both
    `(b + c * d)` and `(b + (c * d))` evaluate to 14.
    """

    def test_the_forced_form_parses_back_to_the_same_expression(self):
        forced = loads("a = (b + c * d)\n", serialization_options=FORCED)["a"]
        reparsed = loads(f"a = {forced[2:-1]}\n", serialization_options=DEFAULT)["a"]
        self.assertEqual(reparsed, "${(b + (c * d))}")
