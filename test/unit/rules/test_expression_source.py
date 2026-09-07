# pylint: disable=C0103,C0114,C0115,C0116
r"""Rules that are serialized into expression source (GH #340, #341).

`SerializationContext.inside_dollar_string` tells a rule it is being written
into an expression rather than handed to a caller as a value. `StringRule`
checks it and keeps its quotes, because `upper("x")` becoming `upper(x)` asks
for a variable nobody declared. Two rules did not check it.

Both defects are in the value form only -- `strip_string_quotes=True`. What
the other modes emit is unchanged; `TestTheOtherModesAreUntouched` states so,
including the round trip, because that is the half a change here can break
without any of the assertions above noticing.

Checked against Terraform v1.11.4:

    upper(<<EOT\nx\nEOT\n)              -> "X\n", so the argument is a string
    "%{ if local.x == "y" }t%{ endif }" -> "t", with plain quotes

The escaped spelling this grammar also accepts, `\"y\"` inside a directive,
Terraform rejects outright with "Invalid character". That divergence is filed
as #341's sibling, #353; the tests below only pin that the value form stops
mangling it into a reference, which is what #341 asks for.
"""

from unittest import TestCase

from hcl2.api import dumps, loads
from hcl2.utils import SerializationOptions

VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)
QUOTED = SerializationOptions(strip_string_quotes=True)
SOURCE = SerializationOptions(preserve_heredocs=False)
DEFAULT = SerializationOptions()


class TestAHeredocInsideAnExpression(TestCase):
    """#340: the body was spliced in bare, so it read as a reference."""

    def value(self, source: str) -> str:
        return loads(source, serialization_options=VALUE)["a"]

    def test_it_stays_a_string(self):
        self.assertEqual(self.value("a = upper(<<E\nx\nE\n)\n"), '${upper("x")}')

    def test_it_matches_the_quoted_equivalent(self):
        self.assertEqual(
            self.value("a = upper(<<E\nx\nE\n)\n"),
            self.value('a = upper("x")\n'),
        )

    def test_a_multi_line_body_does_not_splice_raw_newlines(self):
        result = self.value("a = upper(<<E\nx\ny\nE\n)\n")
        self.assertEqual(result, '${upper("x\\ny")}')
        self.assertNotIn("\n", result)

    def test_the_trim_form_too(self):
        self.assertEqual(self.value("a = upper(<<-E\n  x\n  E\n)\n"), '${upper("x")}')

    def test_a_heredoc_that_is_not_in_an_expression_is_unaffected(self):
        # Nothing wraps this one, so the caller does get the bare body.
        self.assertEqual(self.value("a = <<E\nx\nE\n"), "x")

    def test_a_heredoc_in_a_container_is_unaffected(self):
        # A tuple element and an object value are values, not expression
        # source, so they keep handing back the body.
        self.assertEqual(self.value("a = [<<E\nx\nE\n]\n"), ["x"])
        self.assertEqual(self.value("a = {k = <<E\nx\nE\n}\n"), {"k": "x"})


class TestEveryExpressionContextQuotesIt(TestCase):
    """`inside_dollar_string` is set by more rules than the function call.

    #340 was reported against an argument, but every rule that marks its
    children as expression source had the same hole. One case each, so a rule
    that stops threading the context is caught here rather than in whichever
    document happens to use it.
    """

    def value(self, source: str) -> str:
        return loads(source, serialization_options=VALUE)["a"]

    def test_a_nested_call(self):
        self.assertEqual(self.value("a = upper(lower(<<E\nx\nE\n))\n"), '${upper(lower("x"))}')

    def test_a_later_argument(self):
        self.assertEqual(self.value('a = join(",", <<E\nx\nE\n)\n'), '${join(",", "x")}')

    def test_a_binary_operand(self):
        self.assertEqual(self.value("a = b + <<E\nx\nE\n"), '${b + "x"}')

    def test_a_conditional_branch(self):
        self.assertEqual(self.value('a = c ? <<E\nx\nE\n : "z"\n'), '${c ? "x" : "z"}')

    def test_an_indexed_tuple_inside_a_call(self):
        self.assertEqual(self.value("a = upper([<<E\nx\nE\n][0])\n"), '${upper(["x"][0])}')

    def test_an_interpolation_in_a_quoted_string(self):
        self.assertEqual(self.value('a = "${upper(<<E\nx\nE\n)}"\n'), '${upper("x")}')

    def test_none_of_them_leak_a_raw_newline(self):
        for source in (
            "a = upper(<<E\nx\ny\nE\n)\n",
            "a = b + <<E\nx\ny\nE\n",
            'a = c ? <<E\nx\ny\nE\n : "z"\n',
        ):
            with self.subTest(source=source):
                self.assertNotIn("\n", self.value(source))


class TestAStringLiteralInsideADirective(TestCase):
    """#341: the delimiters were dropped, turning a literal into a reference."""

    ESCAPED = 'a = "%{ if x == \\"y\\" }t%{ endif }"\n'
    PLAIN = 'a = "%{ if x == "y" }t%{ endif }"\n'

    def test_the_escaped_delimiters_survive_the_value_form(self):
        self.assertEqual(
            loads(self.ESCAPED, serialization_options=QUOTED)["a"], '%{ if x == \\"y\\" }t%{ endif }'
        )

    def test_the_plain_delimiters_survive_too(self):
        # The spelling Terraform accepts; unchanged by this fix, asserted so it
        # stays that way.
        self.assertEqual(loads(self.PLAIN, serialization_options=QUOTED)["a"], '%{ if x == "y" }t%{ endif }')

    def test_the_literal_is_not_reduced_to_a_reference(self):
        # The point of the fix: `== y` would compare against a variable.
        for source in (self.ESCAPED, self.PLAIN):
            with self.subTest(source=source):
                self.assertNotIn("== y ", loads(source, serialization_options=QUOTED)["a"])

    def test_the_source_form_is_unchanged(self):
        self.assertEqual(loads(self.ESCAPED)["a"], '"%{ if x == \\"y\\" }t%{ endif }"')

    def test_a_directive_without_a_literal_is_unaffected(self):
        self.assertEqual(
            loads('a = "%{ if x }t%{ endif }"\n', serialization_options=QUOTED)["a"],
            "%{ if x }t%{ endif }",
        )


class TestTheOtherModesAreUntouched(TestCase):
    """Neither fix changes what the non-value modes emit, or the round trip."""

    HEREDOC_IN_EXPRESSION = (
        "a = upper(<<E\nx\nE\n)\n",
        "a = trimspace(<<EOF\nhi\nEOF\n)\n",
        "a = trimspace(<<EOF\nEOF\n)\n",
        "a = b + <<E\nx\nE\n",
    )

    def test_a_heredoc_argument_keeps_its_quoted_source(self):
        self.assertEqual(
            loads("a = upper(<<E\nx\nE\n)\n", serialization_options=SOURCE)["a"], '${upper("x")}'
        )

    def test_default_options_keep_the_heredoc_as_quoted_source(self):
        r"""The default still quotes the heredoc's own text, markers and all.

        That form is not valid HCL -- Terraform rejects a quoted string split
        over lines with "Invalid multi-line string", and a heredoc is a legal
        argument as itself. Changing it needs the emitting side to give a
        heredoc its own line first, which is #338; until then this asserts what
        the default does rather than what it should, so the two fixes here stay
        confined to the value form.
        """
        self.assertEqual(loads("a = upper(<<E\nx\nE\n)\n")["a"], '${upper("<<E\nx\nE")}')

    def test_the_default_dict_still_round_trips(self):
        # `dumps` has to read back whatever `loads` produced. Emitting the
        # heredoc unquoted here breaks this, which is why that belongs with
        # #338 rather than in this change.
        for source in self.HEREDOC_IN_EXPRESSION:
            with self.subTest(source=source):
                written = dumps(loads(source, serialization_options=DEFAULT))
                self.assertEqual(dumps(loads(written)), written)

    def test_the_value_dict_still_round_trips(self):
        for source in self.HEREDOC_IN_EXPRESSION:
            with self.subTest(source=source):
                written = dumps(loads(source, serialization_options=VALUE))
                self.assertEqual(dumps(loads(written)), written)
