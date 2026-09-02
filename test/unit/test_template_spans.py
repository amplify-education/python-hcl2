# pylint: disable=C0103,C0114,C0115,C0116
r"""Escapes belong to the span they are written in (GH #329, #336, #339).

A quoted string or a heredoc body is not one run of literal characters. HCL
reads `${...}` and `%{...}` as expression source, and `$${`/`%%{` as escapes
for a literal `${`/`%{`. Three defects came from ignoring that:

* the writer resolved four escapes where the reader resolves nine (#329),
* `$${` and `%%{` were returned doubled by the value form, which is not what
  Terraform evaluates them to (#336),
* and both the escaping and the unescaping ran over interpolation text, which
  belongs to an expression rather than to this string (#339).

Every expectation below was checked against OpenTofu v1.12.5.
"""

from unittest import TestCase

from hcl2.api import dumps, loads
from hcl2.deserializer import DeserializerOptions
from hcl2.template import INTERPOLATION, LITERAL, split_template
from hcl2.utils import SerializationOptions

FLAT = SerializationOptions(preserve_heredocs=False)
VALUE = SerializationOptions(preserve_heredocs=False, strip_string_quotes=True)
QUOTED_VALUE = SerializationOptions(strip_string_quotes=True)
HEREDOCS = DeserializerOptions(strings_to_heredocs=True)


class TestSplitTemplate(TestCase):
    def test_plain_text_is_one_literal(self):
        self.assertEqual(list(split_template("plain")), [(LITERAL, "plain")])

    def test_an_interpolation_is_its_own_span(self):
        self.assertEqual(
            list(split_template('a${upper("x")}b')),
            [(LITERAL, "a"), (INTERPOLATION, '${upper("x")}'), (LITERAL, "b")],
        )

    def test_an_escaped_marker_stays_literal(self):
        # The `${` inside `$${` must not open a span -- which is why the scan
        # cannot be split into "find boundaries" then "resolve escapes".
        self.assertEqual(list(split_template("a$${esc}b")), [(LITERAL, "a$${esc}b")])
        self.assertEqual(list(split_template("a%%{d}b")), [(LITERAL, "a%%{d}b")])

    def test_braces_inside_a_nested_string_do_not_close_the_span(self):
        self.assertEqual(list(split_template('${ {k = "}"} }')), [(INTERPOLATION, '${ {k = "}"} }')])

    def test_a_directive_is_expression_source_too(self):
        self.assertEqual(
            list(split_template("%{ if x }t%{ endif }")),
            [
                (INTERPOLATION, "%{ if x }"),
                (LITERAL, "t"),
                (INTERPOLATION, "%{ endif }"),
            ],
        )

    def test_an_unbalanced_span_is_not_an_error(self):
        # A serializer is the wrong place to reject what the parser accepted.
        self.assertEqual(list(split_template("x ${a")), [(LITERAL, "x "), (INTERPOLATION, "${a")])


class TestTheValueResolvesTheTemplateEscapes(TestCase):
    """`$${` and `%%{` stand for a literal `${` and `%{`, so the value has one."""

    def test_in_a_quoted_string(self):
        self.assertEqual(loads('a = "$${esc}"\n', serialization_options=QUOTED_VALUE)["a"], "${esc}")
        self.assertEqual(loads('a = "%%{d}"\n', serialization_options=QUOTED_VALUE)["a"], "%{d}")

    def test_in_a_heredoc(self):
        self.assertEqual(loads("a = <<EOT\n$${esc}\nEOT\n", serialization_options=VALUE)["a"], "${esc}\n")
        self.assertEqual(loads("a = <<EOT\n%%{d}\nEOT\n", serialization_options=VALUE)["a"], "%{d}\n")

    def test_in_a_trimmed_heredoc(self):
        self.assertEqual(
            loads("a = <<-EOT\n  $${esc}\n  EOT\n", serialization_options=VALUE)["a"], "${esc}\n"
        )

    def test_a_real_interpolation_is_left_alone(self):
        self.assertEqual(loads("a = <<EOT\n${keep}\nEOT\n", serialization_options=VALUE)["a"], "${keep}\n")

    def test_a_doubled_sigil_without_a_brace_is_not_an_escape(self):
        self.assertEqual(loads('a = "$$x %%y"\n', serialization_options=QUOTED_VALUE)["a"], "$$x %%y")


class TestTheWriterResolvesEveryEscape(TestCase):
    """A heredoc body is literal, so the quoted form's escapes must be resolved.

    The writer knew four of them, while the reader resolves nine, so `\t` was
    written into the body as a backslash and a `t` -- two characters where
    Terraform reads one tab.
    """

    def _body(self, value: str) -> str:
        return dumps({"a": value}, deserializer_options=HEREDOCS)

    def test_a_tab_becomes_a_tab(self):
        self.assertEqual(self._body(r'"a\tb\n"'), "a = <<EOF\na\tb\nEOF\n")

    def test_a_unicode_escape_becomes_its_character(self):
        self.assertEqual(self._body(r'"café\n"'), "a = <<EOF\ncafé\nEOF\n")

    def test_a_wide_unicode_escape_becomes_its_character(self):
        self.assertEqual(self._body(r'"\U0001F600\n"'), "a = <<EOF\n\U0001f600\nEOF\n")


class TestEscapesDoNotCrossIntoAnExpression(TestCase):
    r"""Inside `${...}` the text belongs to an expression, not to this string.

    OpenTofu reads `"${upper("a")}"` as `A` and rejects `"${upper(\"a\")}"`
    outright, so escaping through an interpolation does not merely look wrong:
    it produces source the reference implementation will not parse. In the
    other direction `"${upper("a\"b")}"` is `A"B`, so resolving that `\"` would
    close the nested literal early.
    """

    def test_flattening_leaves_the_interpolation_verbatim(self):
        self.assertEqual(
            loads('a = <<EOT\n${upper("a")}\nEOT\n', serialization_options=FLAT)["a"],
            '"${upper("a")}\\n"',
        )

    def test_flattening_still_escapes_the_literal_text_around_it(self):
        self.assertEqual(
            loads('a = <<EOT\nsay "hi" ${x}\nEOT\n', serialization_options=FLAT)["a"],
            '"say \\"hi\\" ${x}\\n"',
        )

    def test_writing_leaves_a_nested_literals_escape_alone(self):
        self.assertEqual(
            dumps({"a": '"${upper("a\\"b")}\\n"'}, deserializer_options=HEREDOCS),
            'a = <<EOF\n${upper("a\\"b")}\nEOF\n',
        )

    def test_the_pair_round_trips(self):
        source = 'a = <<EOT\n${upper("a")}\nEOT\n'
        flattened = loads(source, serialization_options=FLAT)
        restored = dumps(flattened, deserializer_options=HEREDOCS)
        self.assertEqual(
            loads(restored, serialization_options=VALUE)["a"],
            loads(source, serialization_options=VALUE)["a"],
        )


class TestBracesThatAreNotStructural(TestCase):
    r"""Three things inside an expression may carry a brace that does not nest.

    A string literal was handled from the start. Comments were not, and HCL
    writes them three ways: OpenTofu evaluates `${1 /* } */ + 2}` to 3, so a
    scan that counts that brace closes the expression inside itself and hands
    the rest back as literal text -- which flattening then escapes, rewriting
    expression source.
    """

    def test_a_brace_in_a_block_comment(self):
        self.assertEqual(
            list(split_template("${1 /* } */ + 2}")), [(INTERPOLATION, "${1 /* } */ + 2}")]
        )

    def test_a_brace_in_a_hash_comment(self):
        self.assertEqual(
            list(split_template('${ foo( # }\n  "a") }')),
            [(INTERPOLATION, '${ foo( # }\n  "a") }')],
        )

    def test_a_brace_in_a_slash_comment(self):
        self.assertEqual(
            list(split_template("${ a // }\n }")), [(INTERPOLATION, "${ a // }\n }")]
        )

    def test_a_brace_in_a_string_literal(self):
        self.assertEqual(
            list(split_template('${ {k = "}"} }')), [(INTERPOLATION, '${ {k = "}"} }')]
        )

    def test_an_unterminated_comment_does_not_hang(self):
        self.assertEqual(list(split_template("${ a /* } ")), [(INTERPOLATION, "${ a /* } ")])

    def test_flattening_leaves_a_commented_expression_alone(self):
        self.assertEqual(
            loads('a = <<EOT\n${1 /* } */ + 2}\nEOT\n', serialization_options=FLAT)["a"],
            '"${1 /* } */ + 2}\\n"',
        )
