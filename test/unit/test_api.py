# pylint: disable=C0103,C0114,C0115,C0116
from io import StringIO
from unittest import TestCase

from lark.tree import Tree

from hcl2.api import (
    dump,
    dumps,
    from_dict,
    from_json,
    load,
    loads,
    parse,
    parse_to_tree,
    parses,
    parses_to_tree,
    query,
    reconstruct,
    serialize,
    transform,
)
from hcl2.deserializer import DeserializerOptions
from hcl2.formatter import FormatterOptions
from hcl2.rules.base import StartRule
from hcl2.utils import SerializationOptions

SIMPLE_HCL = "x = 5\n"
SIMPLE_DICT = {"x": 5}

BLOCK_HCL = 'resource "aws_instance" "example" {\n  ami = "abc-123"\n}\n'


class TestLoads(TestCase):
    def test_simple_attribute(self):
        result = loads(SIMPLE_HCL)
        self.assertEqual(result["x"], 5)

    def test_returns_dict(self):
        result = loads(SIMPLE_HCL)
        self.assertIsInstance(result, dict)

    def test_with_serialization_options(self):
        result = loads(SIMPLE_HCL, serialization_options=SerializationOptions(with_comments=False))
        self.assertIsInstance(result, dict)
        self.assertEqual(result["x"], 5)

    def test_with_meta_option(self):
        result = loads(BLOCK_HCL, serialization_options=SerializationOptions(with_meta=True))
        self.assertIn("resource", result)
        # Verify the option is accepted and produces a dict with expected content
        self.assertIsInstance(result, dict)

    def test_block_parsing(self):
        result = loads(BLOCK_HCL)
        self.assertIn("resource", result)

    def test_strip_string_quotes(self):
        result = loads(
            BLOCK_HCL,
            serialization_options=SerializationOptions(strip_string_quotes=True, explicit_blocks=False),
        )
        resource_list = result["resource"]
        self.assertEqual(len(resource_list), 1)
        block = resource_list[0]
        # Block label should have no surrounding quotes
        self.assertIn("aws_instance", block)
        inner = block["aws_instance"]
        self.assertIn("example", inner)
        body = inner["example"]
        # Attribute value should have no surrounding quotes
        self.assertEqual(body["ami"], "abc-123")
        # No __is_block__ marker
        self.assertNotIn("__is_block__", body)


class TestLoad(TestCase):
    def test_from_file(self):
        f = StringIO(SIMPLE_HCL)
        result = load(f)
        self.assertEqual(result["x"], 5)

    def test_with_serialization_options(self):
        f = StringIO(SIMPLE_HCL)
        result = load(f, serialization_options=SerializationOptions(with_comments=False))
        self.assertEqual(result["x"], 5)


class TestDumps(TestCase):
    def test_simple_attribute(self):
        result = dumps(SIMPLE_DICT)
        self.assertIsInstance(result, str)
        self.assertIn("x", result)
        self.assertIn("5", result)

    def test_dumps_contains_key_and_value(self):
        result = dumps(SIMPLE_DICT)
        self.assertIn("x", result)
        self.assertIn("5", result)

    def test_roundtrip(self):
        result = loads(dumps(SIMPLE_DICT))
        self.assertEqual(result, SIMPLE_DICT)

    def test_with_deserializer_options(self):
        result = dumps(SIMPLE_DICT, deserializer_options=DeserializerOptions())
        self.assertIsInstance(result, str)

    def test_with_formatter_options(self):
        result = dumps(SIMPLE_DICT, formatter_options=FormatterOptions())
        self.assertIsInstance(result, str)


class TestDump(TestCase):
    def test_writes_to_file(self):
        f = StringIO()
        dump(SIMPLE_DICT, f)
        output = f.getvalue()
        self.assertIn("x", output)
        self.assertIn("5", output)


class TestParsesToTree(TestCase):
    def test_returns_lark_tree(self):
        result = parses_to_tree(SIMPLE_HCL)
        self.assertIsInstance(result, Tree)

    def test_tree_has_start_rule(self):
        result = parses_to_tree(SIMPLE_HCL)
        self.assertEqual(result.data, "start")


class TestParseToTree(TestCase):
    def test_from_file(self):
        f = StringIO(SIMPLE_HCL)
        result = parse_to_tree(f)
        self.assertIsInstance(result, Tree)


class TestParses(TestCase):
    def test_returns_start_rule(self):
        result = parses(SIMPLE_HCL)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments_false(self):
        hcl = "# comment\nx = 5\n"
        result = parses(hcl, discard_comments=False)
        serialized = serialize(result)
        self.assertIn("__comments__", serialized)

    def test_discard_comments_true(self):
        hcl = "# comment\nx = 5\n"
        result = parses(hcl, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestParse(TestCase):
    def test_from_file(self):
        f = StringIO(SIMPLE_HCL)
        result = parse(f)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments(self):
        f = StringIO("# comment\nx = 5\n")
        result = parse(f, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestTransform(TestCase):
    def test_transforms_lark_tree(self):
        lark_tree = parses_to_tree(SIMPLE_HCL)
        result = transform(lark_tree)
        self.assertIsInstance(result, StartRule)

    def test_discard_comments(self):
        lark_tree = parses_to_tree("# comment\nx = 5\n")
        result = transform(lark_tree, discard_comments=True)
        serialized = serialize(result)
        self.assertNotIn("__comments__", serialized)


class TestSerialize(TestCase):
    def test_returns_dict(self):
        tree = parses(SIMPLE_HCL)
        result = serialize(tree)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["x"], 5)

    def test_with_options(self):
        tree = parses(SIMPLE_HCL)
        result = serialize(tree, serialization_options=SerializationOptions(with_comments=False))
        self.assertIsInstance(result, dict)

    def test_none_options_uses_defaults(self):
        tree = parses(SIMPLE_HCL)
        result = serialize(tree, serialization_options=None)
        self.assertEqual(result["x"], 5)


class TestFromDict(TestCase):
    def test_returns_start_rule(self):
        result = from_dict(SIMPLE_DICT)
        self.assertIsInstance(result, StartRule)

    def test_roundtrip(self):
        tree = from_dict(SIMPLE_DICT)
        result = serialize(tree)
        self.assertEqual(result["x"], 5)

    def test_without_formatting(self):
        result = from_dict(SIMPLE_DICT, apply_format=False)
        self.assertIsInstance(result, StartRule)

    def test_with_deserializer_options(self):
        result = from_dict(SIMPLE_DICT, deserializer_options=DeserializerOptions())
        self.assertIsInstance(result, StartRule)

    def test_with_formatter_options(self):
        result = from_dict(SIMPLE_DICT, formatter_options=FormatterOptions())
        self.assertIsInstance(result, StartRule)


class TestFromJson(TestCase):
    def test_returns_start_rule(self):
        result = from_json('{"x": 5}')
        self.assertIsInstance(result, StartRule)

    def test_roundtrip(self):
        tree = from_json('{"x": 5}')
        result = serialize(tree)
        self.assertEqual(result["x"], 5)

    def test_without_formatting(self):
        result = from_json('{"x": 5}', apply_format=False)
        self.assertIsInstance(result, StartRule)


class TestReconstruct(TestCase):
    def test_from_start_rule(self):
        tree = parses(SIMPLE_HCL)
        result = reconstruct(tree)
        self.assertIsInstance(result, str)
        self.assertIn("x", result)

    def test_from_lark_tree(self):
        lark_tree = parses_to_tree(SIMPLE_HCL)
        result = reconstruct(lark_tree)
        self.assertIsInstance(result, str)
        self.assertIn("x", result)

    def test_roundtrip(self):
        tree = parses(SIMPLE_HCL)
        hcl_text = reconstruct(tree)
        reparsed = loads(hcl_text)
        self.assertEqual(reparsed["x"], 5)


class TestErrorPaths(TestCase):
    def test_loads_raises_on_invalid_hcl(self):
        with self.assertRaises(Exception):
            loads("this is {{{{ not valid hcl")

    def test_dumps_on_non_dict_raises_type_error(self):
        with self.assertRaises(TypeError):
            dumps("not a dict")

    def test_from_json_raises_on_invalid_json(self):
        with self.assertRaises(Exception):
            from_json("{not valid json")


class TestQuery(TestCase):
    def test_query_string(self):
        from hcl2.query.body import DocumentView

        result = query(SIMPLE_HCL)
        self.assertIsInstance(result, DocumentView)
        attr = result.attribute("x")
        self.assertIsNotNone(attr)

    def test_query_file_object(self):
        from hcl2.query.body import DocumentView

        f = StringIO(SIMPLE_HCL)
        result = query(f)
        self.assertIsInstance(result, DocumentView)
        attr = result.attribute("x")
        self.assertIsNotNone(attr)


class TestEmptyHeredocs(TestCase):
    """A heredoc with no body parses, and does not swallow what follows.

    The v8 grammar made the newline before the closing delimiter mandatory, so
    a marker immediately followed by its delimiter could not match. The lexer
    then scanned on to a later delimiter, which silently absorbed the
    intervening attributes rather than reporting an error.
    """

    def test_empty_heredoc_parses(self):
        self.assertEqual(loads("a = <<EOF\nEOF\n"), {"a": '"<<EOF\nEOF"'})

    def test_empty_trimmed_heredoc_parses(self):
        self.assertEqual(loads("a = <<-EOF\n  EOF\n"), {"a": '"<<-EOF\n  EOF"'})

    def test_empty_heredoc_flattens_to_empty_string(self):
        options = SerializationOptions(preserve_heredocs=False)
        self.assertEqual(loads("a = <<EOF\nEOF\n", serialization_options=options), {"a": '""'})

    def test_empty_heredoc_does_not_swallow_following_attributes(self):
        source = "a = <<EOF\nEOF\n\nb = <<EOF\nreal body\nEOF\n\nc = 1\n"
        self.assertEqual(
            loads(source),
            {"a": '"<<EOF\nEOF"', "b": '"<<EOF\nreal body\nEOF"', "c": 1},
        )

    def test_heredoc_with_a_blank_body_line_is_distinct_from_empty(self):
        self.assertEqual(loads("a = <<EOF\n\nEOF\n"), {"a": '"<<EOF\n\nEOF"'})

    def test_delimiter_must_start_its_own_line(self):
        """A word merely ending in the delimiter does not terminate the body."""
        self.assertEqual(loads("a = <<EOF\nsayEOF\nEOF\n"), {"a": '"<<EOF\nsayEOF\nEOF"'})

    def test_body_containing_the_delimiter_as_a_prefix(self):
        self.assertEqual(loads("a = <<EOF\nEOF_NOT\nEOF\n"), {"a": '"<<EOF\nEOF_NOT\nEOF"'})

    def test_consecutive_heredocs_stay_separate(self):
        source = "a = <<EOF\nx\nEOF\nb = <<EOF\ny\nEOF\n"
        self.assertEqual(loads(source), {"a": '"<<EOF\nx\nEOF"', "b": '"<<EOF\ny\nEOF"'})

    def test_indented_closing_delimiter_still_allowed(self):
        self.assertEqual(loads("a = <<EOF\nx\n   EOF\n"), {"a": '"<<EOF\nx\n   EOF"'})

    def test_two_consecutive_empty_heredocs_stay_separate(self):
        """The tightest form of the run-on: nothing between the two markers.

        Before the fix this returned a single attribute whose value spanned
        both, with `b` absent and no exception raised.
        """
        source = "a = <<EOF\nEOF\nb = <<EOF\nEOF\n"
        self.assertEqual(loads(source), {"a": '"<<EOF\nEOF"', "b": '"<<EOF\nEOF"'})

    def test_empty_heredoc_before_a_different_delimiter(self):
        """The run-on latched onto any later delimiter, not just a matching one."""
        source = "a = <<AAA\nAAA\nb = <<BBB\nbody\nBBB\n"
        self.assertEqual(loads(source), {"a": '"<<AAA\nAAA"', "b": '"<<BBB\nbody\nBBB"'})

    def test_empty_trimmed_heredoc_with_tab_indented_delimiter(self):
        """`\\s*` before the delimiter covers tabs, not just spaces."""
        self.assertEqual(loads("a = <<-EOF\n\tEOF\n"), {"a": '"<<-EOF\n\tEOF"'})

    def test_empty_heredoc_in_a_tuple(self):
        self.assertEqual(loads("a = [<<EOF\nEOF\n]\n"), {"a": ['"<<EOF\nEOF"']})

    def test_empty_heredoc_as_an_object_value(self):
        self.assertEqual(loads("a = {\n  k = <<EOF\nEOF\n}\n"), {"a": {"k": '"<<EOF\nEOF"'}})

    def test_empty_heredoc_as_a_function_argument(self):
        self.assertEqual(loads("a = trimspace(<<EOF\nEOF\n)\n"), {"a": '${trimspace("<<EOF\nEOF")}'})


class TestNegativeIntegerLiterals(TestCase):
    """`-3` loads as the int -3, without disturbing subtraction.

    MINUS serves as both the unary sign and the binary subtraction operator, so
    a negative integer cannot be folded into INT_LITERAL by the lexer without
    breaking `10 -3`. These cases pin both halves of that trade-off.
    """

    def test_negative_int_is_an_int(self):
        self.assertEqual(loads("x = -3\n"), {"x": -3})

    def test_negative_int_matches_negative_float_handling(self):
        self.assertEqual(loads("x = -3\ny = -3.5\n"), {"x": -3, "y": -3.5})

    def test_negative_ints_in_tuple(self):
        self.assertEqual(loads("x = [-1, 2, -30]\n"), {"x": [-1, 2, -30]})

    def test_negative_ints_in_object(self):
        self.assertEqual(loads("x = { a = -1, b = 2 }\n"), {"x": {"a": -1, "b": 2}})

    def test_spaced_subtraction_is_still_an_expression(self):
        self.assertEqual(loads("x = 10 - 3\n"), {"x": "${10 - 3}"})

    def test_tight_subtraction_is_still_an_expression(self):
        """`10 -3` is a subtraction, not two adjacent literals."""
        self.assertEqual(loads("x = 10 -3\n"), {"x": "${10 - 3}"})

    def test_negated_reference_is_still_an_expression(self):
        self.assertEqual(loads("x = -var.count\n"), {"x": "${-var.count}"})

    def test_negation_inside_a_larger_expression(self):
        self.assertEqual(loads("x = 1 + -3\n"), {"x": "${1 + -3}"})

    def test_parenthesised_negation_is_still_an_expression(self):
        self.assertEqual(loads("x = -(3)\n"), {"x": "${-(3)}"})

    def test_scientific_notation_is_unaffected(self):
        """`-1e10` never reaches the unary path: it lexes as a single FLOAT_LITERAL."""
        self.assertEqual(loads("x = -1e10\n"), {"x": "${-1e10}"})

    def test_spaced_negation_of_scientific_notation_stays_an_expression(self):
        """The spaced form *is* a unary op, and its operand is a string.

        `preserve_scientific_notation` (on by default) keeps `1e10` as source
        text, so there is no number to negate and the expression form stands.
        """
        self.assertEqual(loads("x = - 1e10\n"), {"x": "${-1e10}"})

    def test_spaced_negation_of_integer_is_still_a_number(self):
        self.assertEqual(loads("x = - 3\n"), {"x": -3})

    def test_negative_zero_normalises_to_zero(self):
        """`-0` is 0. The dict path drops the sign; the direct path keeps the source."""
        self.assertEqual(loads("x = -0\n"), {"x": 0})
        self.assertEqual(dumps(loads("x = -0\n")), "x = 0\n")

    def test_round_trip_through_dumps(self):
        self.assertEqual(loads(dumps(loads("x = -3\n"))), {"x": -3})


class TestNegatedKeywords(TestCase):
    """`-true` is not arithmetic, so it stays an expression.

    This is the parsed counterpart to the `bool` guard in
    `UnaryOpRule._negate_numeric_literal`: a keyword operand is serialized with
    `inside_dollar_string` set and so arrives as the string "true", never as a
    Python bool. Without that distinction `bool` subclassing `int` would turn
    `-true` into -1.
    """

    def test_negated_true(self):
        self.assertEqual(loads("x = -true\n"), {"x": "${-true}"})

    def test_negated_false(self):
        self.assertEqual(loads("x = -false\n"), {"x": "${-false}"})

    def test_negated_null(self):
        self.assertEqual(loads("x = -null\n"), {"x": "${-null}"})

    def test_not_operator_on_keyword(self):
        self.assertEqual(loads("x = !true\n"), {"x": "${!true}"})

    def test_bare_keywords_are_still_python_values(self):
        """Outside an expression the keywords keep their Python mappings."""
        self.assertEqual(loads("x = true\ny = false\nz = null\n"), {"x": True, "y": False, "z": None})


class TestStripStringQuotes(TestCase):
    """`strip_string_quotes=True` asks for values, not source text.

    It is the documented v7-compatibility path, so it has to yield what v7
    yielded: quotes removed from string *values*, escape sequences resolved,
    and expressions left as valid HCL.
    """

    _OPTIONS = SerializationOptions(strip_string_quotes=True)

    def _load(self, source):
        return loads(source, serialization_options=self._OPTIONS)

    def test_plain_value_loses_its_quotes(self):
        self.assertEqual(self._load('a = "plain"\n'), {"a": "plain"})

    def test_value_in_object_and_list(self):
        self.assertEqual(
            self._load('a = { k = "v" }\nb = ["x"]\n'),
            {"a": {"k": "v"}, "b": ["x"]},
        )

    def test_function_argument_keeps_its_quotes(self):
        """Unquoting here would turn a string into an identifier."""
        self.assertEqual(self._load('a = upper("x")\n'), {"a": '${upper("x")}'})

    def test_conditional_branches_keep_their_quotes(self):
        self.assertEqual(
            self._load('a = var.x ? "yes" : "no"\n'),
            {"a": '${var.x ? "yes" : "no"}'},
        )

    def test_comparison_against_a_string_keeps_its_quotes(self):
        """An unquoted empty string would leave `s != ` behind."""
        self.assertEqual(
            self._load('a = [for s in var.l : upper(s) if s != ""]\n'),
            {"a": '${[for s in var.l : upper(s) if s != ""]}'},
        )

    def test_nested_call_keeps_every_quote(self):
        self.assertEqual(
            self._load('a = join(",", ["x", "y"])\n'),
            {"a": '${join(",", ["x", "y"])}'},
        )

    def test_escaped_quote_is_resolved(self):
        self.assertEqual(self._load(r'a = "quote \"in\" here"' + "\n"), {"a": 'quote "in" here'})

    def test_escaped_whitespace_is_resolved(self):
        self.assertEqual(self._load(r'a = "x\ny\tz"' + "\n"), {"a": "x\ny\tz"})

    def test_escaped_backslash_is_resolved(self):
        self.assertEqual(self._load(r'a = "back\\slash"' + "\n"), {"a": "back\\slash"})

    def test_escaped_backslash_does_not_combine_with_the_next_character(self):
        r"""`\\n` is a backslash followed by "n", not a newline."""
        self.assertEqual(self._load(r'a = "back\\nslash"' + "\n"), {"a": "back\\nslash"})

    def test_unknown_escape_is_preserved(self):
        self.assertEqual(self._load(r'a = "keep \q intact"' + "\n"), {"a": r"keep \q intact"})

    def test_out_of_range_unicode_escape_does_not_raise(self):
        """An unusable codepoint is preserved, not propagated as an exception.

        `\\U00110000` makes `chr` raise ValueError and `\\UFFFFFFFF` makes it
        raise OverflowError; neither is the serializer's error to raise, since
        the grammar accepted the input.
        """
        self.assertEqual(self._load(r'a = "X\U00110000Y"' + "\n"), {"a": r"X\U00110000Y"})
        self.assertEqual(self._load(r'a = "X\UFFFFFFFFY"' + "\n"), {"a": r"X\UFFFFFFFFY"})

    def test_lone_surrogate_escape_stays_encodable(self):
        """Decoding it would yield a value that cannot be written out as UTF-8."""
        result = self._load(r'a = "X\uD800Y"' + "\n")
        self.assertEqual(result, {"a": r"X\uD800Y"})
        result["a"].encode("utf-8")

    def test_interpolation_is_left_alone(self):
        self.assertEqual(self._load('a = "pre${var.x}post"\n'), {"a": "pre${var.x}post"})

    def test_escaped_interpolation_marker_is_left_alone(self):
        self.assertEqual(self._load('a = "lit $${x}"\n'), {"a": "lit $${x}"})

    def test_default_options_still_preserve_source_form(self):
        """Without the option, the source form is kept for reconstruction."""
        self.assertEqual(loads(r'a = "line1\nline2"' + "\n"), {"a": r'"line1\nline2"'})


class TestSingleCharacterHeredocDelimiter(TestCase):
    """`<<E` is a valid heredoc; the delimiter may be one character.

    The spec defines the delimiter as an Identifier — `ID_Start (ID_Continue |
    '-')*` — whose trailing `*` permits a single character. The grammar used
    `+`, which required a second one, so `<<E` fell through to STRING_CHARS and
    the parse failed.
    """

    def test_single_character_delimiter(self):
        self.assertEqual(loads("a = <<E\nx\nE\n"), {"a": '"<<E\nx\nE"'})

    def test_single_character_delimiter_trimmed(self):
        self.assertEqual(loads("a = <<-E\n  x\n  E\n"), {"a": '"<<-E\n  x\n  E"'})

    def test_single_character_delimiter_empty_body(self):
        self.assertEqual(loads("a = <<E\nE\n"), {"a": '"<<E\nE"'})

    def test_single_character_delimiter_flattens(self):
        options = SerializationOptions(preserve_heredocs=False)
        self.assertEqual(loads("a = <<E\nx\nE\n", serialization_options=options), {"a": '"x\\n"'})

    def test_single_character_delimiter_does_not_swallow_what_follows(self):
        self.assertEqual(loads("a = <<E\nx\nE\nb = 1\n"), {"a": '"<<E\nx\nE"', "b": 1})

    def test_body_line_ending_in_the_delimiter_still_safe(self):
        """A one-character delimiter makes an accidental match likelier."""
        self.assertEqual(loads("a = <<E\nsayE\nE\n"), {"a": '"<<E\nsayE\nE"'})

    def test_multi_character_delimiter_unaffected(self):
        self.assertEqual(loads("a = <<EOF\nx\nEOF\n"), {"a": '"<<EOF\nx\nEOF"'})


class TestHeredocFlattenedToValue(TestCase):
    """`strip_string_quotes` + `preserve_heredocs=False` yields real newlines.

    The flatten path escapes the body to build a quoted-string *source* form
    (`'"a\\nb"'`). That escaping ran before the `strip_string_quotes` early
    return, so asking for the value handed back escaped source instead: every
    line break arrived as a literal backslash-n. Before this fix no combination
    of options reproduced v7's plain multi-line string.
    """

    _VALUE = SerializationOptions(strip_string_quotes=True, preserve_heredocs=False)
    _SOURCE = SerializationOptions(preserve_heredocs=False)

    def test_value_has_real_newlines(self):
        result = loads("a = <<EOT\nline1\nline2\nEOT\n", serialization_options=self._VALUE)
        self.assertEqual(result, {"a": "line1\nline2\n"})

    def test_trimmed_value_has_real_newlines(self):
        source = "a = <<-EOT\n  line1\n  line2\n  EOT\n"
        result = loads(source, serialization_options=self._VALUE)
        self.assertEqual(result, {"a": "line1\nline2\n"})

    def test_multiline_secret_survives_intact(self):
        """The reported case: a heredoc-defined key block must stay multi-line."""
        source = (
            "keys = {\n"
            "  private = <<-EOT\n"
            "  -----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            "  line1\n"
            "  -----END PGP PRIVATE KEY BLOCK-----\n"
            "  EOT\n"
            "}\n"
        )
        value = loads(source, serialization_options=self._VALUE)["keys"]["private"]
        # Three lines, each terminated by its own newline -- the last included.
        self.assertEqual(value.count("\n"), 3)
        self.assertNotIn("\\n", value)
        self.assertTrue(value.startswith("-----BEGIN"))
        self.assertTrue(value.endswith("KEY BLOCK-----\n"))

    def test_quoted_form_still_escapes(self):
        """Without strip_string_quotes the result is source and must escape."""
        result = loads("a = <<EOT\nline1\nline2\nEOT\n", serialization_options=self._SOURCE)
        self.assertEqual(result, {"a": '"line1\\nline2\\n"'})

    def test_embedded_quote_and_backslash_only_escaped_in_source_form(self):
        source = 'a = <<EOT\nsay "hi"\nback\\slash\nEOT\n'
        self.assertEqual(
            loads(source, serialization_options=self._VALUE),
            {"a": 'say "hi"\nback\\slash\n'},
        )
        self.assertEqual(
            loads(source, serialization_options=self._SOURCE),
            {"a": '"say \\"hi\\"\\nback\\\\slash\\n"'},
        )
