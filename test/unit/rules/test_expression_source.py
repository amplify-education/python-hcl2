# pylint: disable=C0103,C0114,C0115,C0116
r"""Rules that are serialized into expression source (GH #340, #341).

`SerializationContext.inside_dollar_string` tells a rule it is being written
into an expression rather than handed to a caller as a value. `StringRule`
checks it and keeps its quotes, because `upper("x")` becoming `upper(x)` asks
for a variable nobody declared. Two rules did not check it.

Checked against OpenTofu v1.12.5: `upper(<<EOT\nx\nEOT\n)` evaluates to
`"X\n"`, so the argument is a string; and a string literal inside a directive
is written with plain quotes, `"%{ if local.x == "y" }t%{ endif }"`, which
evaluates to `"t"`.
"""

from unittest import TestCase

from hcl2.api import loads
from hcl2.utils import SerializationOptions

VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)
QUOTED = SerializationOptions(strip_string_quotes=True)
SOURCE = SerializationOptions(preserve_heredocs=False)


class TestAHeredocInsideAnExpression(TestCase):
    """#340: the body was spliced in bare, so it read as a reference."""

    def test_it_stays_a_string(self):
        self.assertEqual(loads("a = upper(<<E\nx\nE\n)\n", serialization_options=VALUE)["a"], '${upper("x")}')

    def test_it_matches_the_quoted_equivalent(self):
        self.assertEqual(
            loads("a = upper(<<E\nx\nE\n)\n", serialization_options=VALUE)["a"],
            loads('a = upper("x")\n', serialization_options=VALUE)["a"],
        )

    def test_a_multi_line_body_does_not_splice_raw_newlines(self):
        result = loads("a = upper(<<E\nx\ny\nE\n)\n", serialization_options=VALUE)["a"]
        self.assertEqual(result, '${upper("x\\ny")}')
        self.assertNotIn("\n", result)

    def test_the_trim_form_too(self):
        self.assertEqual(
            loads("a = upper(<<-E\n  x\n  E\n)\n", serialization_options=VALUE)["a"], '${upper("x")}'
        )

    def test_a_heredoc_that_is_not_in_an_expression_is_unaffected(self):
        self.assertEqual(loads("a = <<E\nx\nE\n", serialization_options=VALUE)["a"], "x")


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

    def test_the_source_form_is_unchanged(self):
        self.assertEqual(loads(self.ESCAPED)["a"], '"%{ if x == \\"y\\" }t%{ endif }"')

    def test_a_directive_without_a_literal_is_unaffected(self):
        self.assertEqual(
            loads('a = "%{ if x }t%{ endif }"\n', serialization_options=QUOTED)["a"],
            "%{ if x }t%{ endif }",
        )


class TestTheSourceFormIsUntouched(TestCase):
    """Neither fix changes what the non-value modes emit."""

    def test_a_heredoc_argument_keeps_its_quoted_source(self):
        self.assertEqual(
            loads("a = upper(<<E\nx\nE\n)\n", serialization_options=SOURCE)["a"], '${upper("x")}'
        )

    def test_default_options_keep_the_heredoc_unquoted(self):
        """A heredoc is a legal argument; quoting it is not.

        The quoted form put raw newlines inside a quoted string, which OpenTofu
        rejects with "Invalid multi-line string". As a heredoc it evaluates:
        `trimspace(<<EOF\n  hi  \nEOF\n)` gives "hi".
        """
        self.assertEqual(loads("a = upper(<<E\nx\nE\n)\n")["a"], "${upper(<<E\nx\nE)}")
