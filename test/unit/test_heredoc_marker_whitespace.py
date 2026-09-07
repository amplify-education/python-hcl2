# pylint: disable=C0103,C0114,C0115,C0116
r"""A closing marker may carry trailing whitespace (GH #343).

The spec puts the delimiter "alone on its own line", and Terraform's scanner
ends the heredoc at a line holding the word and nothing else that matters --
trailing spaces and tabs included. `HEREDOC_TEMPLATE` required the newline to
follow the word immediately, so `EOF  ` was not a marker: the heredoc ran on,
swallowed the rest of the file, and the parse failed with an error pointing
somewhere else entirely.

Trailing whitespace is invisible, survives copy-paste, and is left behind by
editors that do not trim it, so a file someone has been running through
Terraform for months could fail here.

Every expectation below was checked against Terraform v1.11.4:

    <<EOF\nbody\nEOF  \n            -> "body\n", and the next attribute reads
    <<EOF\nEOF  \nb = 1\n           -> "", and b reads as 1
    <<EOF\nEOFX\nEOF x\nbody\nEOF   -> "EOFX\nEOF x\nbody\n"

The value assertions compare a marker carrying trailing whitespace against the
same heredoc without it, rather than pinning an absolute string. The two must
agree whatever the body-value rules are, so stating it as an equality keeps
these tests honest across the separate fixes to those rules (GH #326).
"""

from unittest import TestCase

from hcl2.api import loads, parses_to_tree, reconstruct, transform
from hcl2.utils import SerializationOptions

VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)


def value_of(src: str) -> str:
    """Return the body that the heredoc assigned to `a` evaluates to."""
    return loads(src, serialization_options=VALUE)["a"]


class TestATrailingSpaceClosesTheHeredoc(TestCase):
    """The attribute after the heredoc is reached, so the marker closed it."""

    def test_spaces(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF  \nb = 1\n")["b"], 1)

    def test_a_tab(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF\t\nb = 1\n")["b"], 1)

    def test_mixed(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF \t \nb = 1\n")["b"], 1)

    def test_the_trim_form_too(self):
        self.assertEqual(loads("a = <<-EOF\n  body\n  EOF  \nb = 1\n")["b"], 1)


class TestTheWhitespaceIsNotPartOfTheValue(TestCase):
    """A marker's trailing whitespace belongs to the marker, not the body."""

    def test_spaces_give_the_same_value_as_no_spaces(self):
        self.assertEqual(
            value_of("a = <<EOF\nbody\nEOF  \n"),
            value_of("a = <<EOF\nbody\nEOF\n"),
        )

    def test_a_tab_gives_the_same_value(self):
        self.assertEqual(
            value_of("a = <<EOF\nbody\nEOF\t\n"),
            value_of("a = <<EOF\nbody\nEOF\n"),
        )

    def test_the_trim_form_gives_the_same_value(self):
        self.assertEqual(
            value_of("a = <<-EOF\n  body\n  EOF  \n"),
            value_of("a = <<-EOF\n  body\n  EOF\n"),
        )

    def test_crlf_gives_the_same_value(self):
        self.assertEqual(
            value_of("a = <<EOF\r\nbody\r\nEOF  \r\n"),
            value_of("a = <<EOF\r\nbody\r\nEOF\r\n"),
        )

    def test_the_equality_is_not_vacuous(self):
        # Two empty strings, or two identical failures, would satisfy the
        # tests above without the marker having been recognised at all.
        self.assertIn("body", value_of("a = <<EOF\nbody\nEOF  \n"))

    def test_no_part_of_the_marker_reaches_the_value(self):
        self.assertNotIn("EOF", value_of("a = <<EOF\nbody\nEOF  \n"))
        self.assertNotIn("EOF", value_of("a = <<-EOF\n  body\n  EOF  \n"))


class TestItClosesAtTheFirstSuchLine(TestCase):
    r"""The line that closes it is body text no longer.

    This is the one input whose meaning changes: `EOF  ` used to be content,
    because it was not a marker, and is now the marker. Terraform reads
    `a = <<EOF\nEOF  \nb = 1\n` as an empty string followed by `b = 1`, so
    closing there is what the reference implementation does.
    """

    def test_an_immediate_marker_ends_an_empty_heredoc(self):
        self.assertEqual(value_of("a = <<EOF\nEOF  \n"), "")
        self.assertEqual(loads("a = <<EOF\nEOF  \nb = 1\n")["b"], 1)

    def test_what_follows_it_is_no_longer_swallowed(self):
        # Before the fix the heredoc ran on to the second marker and the value
        # was "EOF  \nmore\n"; now the first line closes it, as Terraform does.
        self.assertNotIn("more", value_of("a = <<EOF\nEOF  \nmore = 1\n"))


class TestWhatIsStillBodyText(TestCase):
    """Only whitespace is allowed after the word; anything else is content."""

    def test_a_word_with_a_suffix_does_not_close_it(self):
        # `EOFX` is not the delimiter, so the heredoc continues past it.
        self.assertIn("EOFX", value_of("a = <<EOF\nEOFX\nbody\nEOF\n"))
        self.assertEqual(loads("a = <<EOF\nEOFX\nbody\nEOF\nb = 1\n")["b"], 1)

    def test_a_marker_with_trailing_text_does_not_close_it(self):
        self.assertIn("EOF x", value_of("a = <<EOF\nEOF x\nbody\nEOF\n"))
        self.assertEqual(loads("a = <<EOF\nEOF x\nbody\nEOF\nb = 1\n")["b"], 1)

    def test_both_together_close_at_the_last_line(self):
        # Terraform reads this as "EOFX\nEOF x\nbody\n".
        body = value_of("a = <<EOF\nEOFX\nEOF x\nbody\nEOF  \n")
        self.assertIn("EOFX", body)
        self.assertIn("EOF x", body)
        self.assertIn("body", body)


class TestTheSourceSurvivesARoundTrip(TestCase):
    """Whitespace the marker carries is written back where it was.

    The marker line is part of the heredoc token, so a reconstruct has to
    reproduce it byte for byte rather than normalise it away.
    """

    def assert_round_trips(self, src: str):
        rules = transform(parses_to_tree(src))
        self.assertEqual(reconstruct(rules.to_lark()), src)

    def test_spaces(self):
        self.assert_round_trips("a = <<EOF\nbody\nEOF  \n")

    def test_a_tab(self):
        self.assert_round_trips("a = <<EOF\nbody\nEOF\t\n")

    def test_the_trim_form(self):
        self.assert_round_trips("a = <<-EOF\n  body\n  EOF  \n")

    def test_an_indented_marker(self):
        self.assert_round_trips("a = <<EOF\nbody\n   EOF  \n")

    def test_crlf(self):
        self.assert_round_trips("a = <<EOF\r\nbody\r\nEOF  \r\n")

    def test_alongside_a_later_attribute(self):
        self.assert_round_trips("a = <<EOF\nbody\nEOF  \nb = 1\n")


class TestNothingElseChanged(TestCase):
    def test_a_plain_marker_still_works(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF\nb = 1\n")["b"], 1)

    def test_an_indented_marker_still_works(self):
        self.assertEqual(loads("a = <<EOF\nbody\n   EOF\nb = 1\n")["b"], 1)

    def test_crlf_still_works(self):
        self.assertEqual(loads("a = <<EOF\r\nbody\r\nEOF\r\nb = 1\r\n")["b"], 1)

    def test_crlf_with_trailing_space(self):
        self.assertEqual(loads("a = <<EOF\r\nbody\r\nEOF  \r\nb = 1\r\n")["b"], 1)
