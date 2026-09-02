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

Checked against OpenTofu v1.12.5: `<<EOF\nbody\nEOF  \n` evaluates to
`"body\n"` and the attribute after it is read normally.
"""

from unittest import TestCase

from hcl2.api import loads


class TestATrailingSpaceClosesTheHeredoc(TestCase):
    def test_spaces(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF  \nb = 1\n")["b"], 1)

    def test_a_tab(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF\t\nb = 1\n")["b"], 1)

    def test_mixed(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF \t \nb = 1\n")["b"], 1)

    def test_the_trim_form_too(self):
        self.assertEqual(loads("a = <<-EOF\n  body\n  EOF  \nb = 1\n")["b"], 1)

    def test_indented_and_trailing_together(self):
        self.assertEqual(loads("a = <<-EOF\n  body\n  EOF  \nb = 1\n")["a"].startswith('"'), True)


class TestWhatIsStillBodyText(TestCase):
    """Only whitespace is allowed after the word; anything else is content."""

    def test_a_word_with_a_suffix_does_not_close_it(self):
        # `EOFX` is not the delimiter, so the heredoc continues past it.
        result = loads("a = <<EOF\nEOFX\nbody\nEOF\nb = 1\n")
        self.assertIn("EOFX", result["a"])
        self.assertEqual(result["b"], 1)

    def test_a_marker_with_trailing_text_does_not_close_it(self):
        result = loads("a = <<EOF\nEOF x\nbody\nEOF\nb = 1\n")
        self.assertIn("EOF x", result["a"])
        self.assertEqual(result["b"], 1)


class TestNothingElseChanged(TestCase):
    def test_a_plain_marker_still_works(self):
        self.assertEqual(loads("a = <<EOF\nbody\nEOF\nb = 1\n")["b"], 1)

    def test_an_indented_marker_still_works(self):
        self.assertEqual(loads("a = <<EOF\nbody\n   EOF\nb = 1\n")["b"], 1)

    def test_crlf_still_works(self):
        self.assertEqual(loads("a = <<EOF\r\nbody\r\nEOF\r\nb = 1\r\n")["b"], 1)

    def test_crlf_with_trailing_space(self):
        self.assertEqual(loads("a = <<EOF\r\nbody\r\nEOF  \r\nb = 1\r\n")["b"], 1)
