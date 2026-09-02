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
from hcl2.rules.strings import _escape_for_quoted_source
from hcl2.template import INTERPOLATION, LITERAL, split_template
from hcl2.utils import SerializationOptions, process_escape_sequences

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

    def test_an_unbalanced_span_is_literal(self):
        """Nothing closes it, so it is text -- and text is what gets escaped.

        Calling it an expression meant nothing escaped it, and the heredoc
        paths then wrote raw newlines and unescaped quotes into what the API
        calls quoted-string source. A serializer is still the wrong place to
        reject what the parser accepted, so this does not raise; it produces
        something well-formed instead.
        """
        self.assertEqual(list(split_template("x ${a")), [(LITERAL, "x ${a")])

    def test_an_unbalanced_span_still_gets_escaped(self):
        self.assertEqual(
            loads('x = <<EOT\nlone ${ open\nsay "hi"\nEOT\n', serialization_options=FLAT)["x"],
            '"lone ${ open\\nsay \\"hi\\"\\n"',
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
        self.assertEqual(list(split_template("${1 /* } */ + 2}")), [(INTERPOLATION, "${1 /* } */ + 2}")])

    def test_a_brace_in_a_hash_comment(self):
        self.assertEqual(
            list(split_template('${ foo( # }\n  "a") }')),
            [(INTERPOLATION, '${ foo( # }\n  "a") }')],
        )

    def test_a_brace_in_a_slash_comment(self):
        self.assertEqual(list(split_template("${ a // }\n }")), [(INTERPOLATION, "${ a // }\n }")])

    def test_a_brace_in_a_string_literal(self):
        self.assertEqual(list(split_template('${ {k = "}"} }')), [(INTERPOLATION, '${ {k = "}"} }')])

    def test_an_unterminated_comment_does_not_hang(self):
        # The comment swallows the closing brace, so nothing closes the span
        # and it is literal by the rule above -- what matters here is that
        # the scan terminates.
        self.assertEqual(list(split_template("${ a /* } ")), [(LITERAL, "${ a /* } ")])

    def test_flattening_leaves_a_commented_expression_alone(self):
        self.assertEqual(
            loads("a = <<EOT\n${1 /* } */ + 2}\nEOT\n", serialization_options=FLAT)["a"],
            '"${1 /* } */ + 2}\\n"',
        )


class TestEscapeResolutionCannotChangeWhatIsCode(TestCase):
    r"""Resolving escapes can spell a sigil that was not in the source.

    `"${foo}"` is the six literal characters `${foo}` to
    Terraform -- escapes resolve at token level and the result is not
    rescanned. Written into a heredoc body, which is not escaped at all, those
    characters are a live interpolation. The reverse happens too:
    `"$${b}"` resolves to `$${b}`, demoting an interpolation to escaped
    text. Either way the value changes, so the conversion is refused and the
    value stays quoted -- as it already does for a lone carriage return.
    """

    def _written(self, value: str) -> str:
        return dumps({"x": value}, deserializer_options=HEREDOCS)

    def test_a_synthesised_sigil_keeps_the_value_quoted(self):
        # The value is `\u0024\u007bfoo\u007d\n`, spelled with chr() so this
        # test's own source cannot be confused with the characters it means.
        esc = chr(92) + "u"
        source = '"' + esc + "0024" + esc + "007bfoo" + esc + "007d" + chr(92) + "n" + '"'
        self.assertEqual(self._written(source), "x = " + source + "\n")

    def test_a_demoted_interpolation_keeps_the_value_quoted(self):
        source = '"' + chr(92) + "u0024" + "${b}" + chr(92) + "n" + '"'
        self.assertEqual(self._written(source), "x = " + source + "\n")

    def test_a_real_interpolation_still_converts(self):
        self.assertEqual(self._written(r'"${b}\n"'), "x = <<EOF\n${b}\nEOF\n")

    def test_an_ordinary_escape_still_converts(self):
        self.assertEqual(self._written(r'"a\tb\n"'), "x = <<EOF\na\tb\nEOF\n")


class TestABackslashPairIsOneUnit(TestCase):
    r"""The scan must not enter string mode at the quote of a `\"`.

    It did, then read the real closing quote as another escape and ran to the
    end of the text -- so a span containing the grammar's own `\"..\"` form
    swallowed everything after it into one interpolation, and the trailing
    newline never reached the writer's newline check.
    """

    def test_an_escaped_quote_does_not_open_a_string(self):
        self.assertEqual(
            list(split_template(r"a\"${f(\"a\")}b")),
            [(LITERAL, r"a\""), (INTERPOLATION, r"${f(\"a\")}"), (LITERAL, "b")],
        )

    def test_an_escaped_quote_inside_a_nested_literal(self):
        self.assertEqual(list(split_template(r'${ "a\"b" }')), [(INTERPOLATION, r'${ "a\"b" }')])


class TestTheEscaperMatchesTheResolver(TestCase):
    r"""The two halves spell the same alphabet, and drift is how #329 happened.

    `process_escape_sequences` resolves seven markers; `_escape_for_quoted_source`
    writes four. The two it does not write -- `\t` and the unicode forms -- are
    deliberate: a tab and an accented character are legal inside a quoted
    string as themselves, so escaping them is unnecessary rather than wrong.
    What matters is that every marker the escaper *does* write is one the
    resolver reads back, so a value survives the round trip.
    """

    ESCAPED = {"\\": "\\\\", '"': '\\"', "\r": "\\r", "\n": "\\n"}

    def test_every_escape_written_is_read_back(self):
        for character, written in self.ESCAPED.items():
            with self.subTest(character=character):
                self.assertEqual(_escape_for_quoted_source(character), written)
                self.assertEqual(process_escape_sequences(written), character)

    def test_a_body_of_every_escaped_character_round_trips(self):
        body = "".join(self.ESCAPED)
        self.assertEqual(process_escape_sequences(_escape_for_quoted_source(body)), body)

    def test_characters_left_unescaped_are_legal_as_themselves(self):
        # A tab and a non-ASCII character need no escape inside a quoted
        # string, so the escaper leaves them; the resolver still reads the
        # escaped spelling if a document uses it.
        self.assertEqual(_escape_for_quoted_source("a\té"), "a\té")
        self.assertEqual(process_escape_sequences(r"a\tb"), "a\tb")
        self.assertEqual(process_escape_sequences(r"café"), "café")


class TestTheWriterResolvesUnicodeEscapes(TestCase):
    r"""The earlier test used a literal e-acute, which passes without the fix."""

    def test_a_bmp_escape_becomes_its_character(self):
        source = '"' + chr(92) + "u00e9" + chr(92) + "n" + '"'
        self.assertEqual(dumps({"a": source}, deserializer_options=HEREDOCS), "a = <<EOF\né\nEOF\n")

    def test_a_wide_escape_becomes_its_character(self):
        source = '"' + chr(92) + "U0001F600" + chr(92) + "n" + '"'
        self.assertEqual(dumps({"a": source}, deserializer_options=HEREDOCS), "a = <<EOF\n\U0001f600\nEOF\n")
