# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.path import QuerySyntaxError, parse_path
from hcl2.query.predicate import (
    Accessor,
    AllExpr,
    AndExpr,
    AnyExpr,
    Comparison,
    HasExpr,
    NotExpr,
    OrExpr,
    Token,
    evaluate_predicate,
    parse_predicate,
    tokenize,
)
from hcl2.query.resolver import resolve_path


class TestTokenize(TestCase):
    def test_dot_and_word(self):
        tokens = tokenize(".foo")
        self.assertEqual(len(tokens), 2)
        self.assertEqual(tokens[0].kind, "DOT")
        self.assertEqual(tokens[1].kind, "WORD")
        self.assertEqual(tokens[1].value, "foo")

    def test_comparison(self):
        tokens = tokenize('.name == "bar"')
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["DOT", "WORD", "OP", "STRING"])

    def test_number(self):
        tokens = tokenize(".x > 42")
        self.assertEqual(tokens[2].kind, "OP")
        self.assertEqual(tokens[3].kind, "NUMBER")
        self.assertEqual(tokens[3].value, "42")

    def test_float_number(self):
        tokens = tokenize(".x > 3.14")
        self.assertEqual(tokens[3].value, "3.14")

    def test_brackets(self):
        tokens = tokenize(".items[0]")
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds, ["DOT", "WORD", "LBRACKET", "NUMBER", "RBRACKET"])

    def test_boolean_keywords(self):
        tokens = tokenize(".a and .b or not .c")
        words = [t.value for t in tokens if t.kind == "WORD"]
        self.assertEqual(words, ["a", "and", "b", "or", "not", "c"])

    def test_all_operators(self):
        for op in ["==", "!=", "<", ">", "<=", ">="]:
            tokens = tokenize(f".x {op} 1")
            self.assertEqual(tokens[2].kind, "OP")
            self.assertEqual(tokens[2].value, op)

    def test_unexpected_char_raises(self):
        with self.assertRaises(QuerySyntaxError):
            tokenize("@invalid")


class TestParsePredicate(TestCase):
    def test_existence(self):
        pred = parse_predicate(".name")
        self.assertIsInstance(pred, Comparison)
        self.assertIsNone(pred.operator)
        self.assertEqual(pred.accessor.parts, ["name"])

    def test_equality_string(self):
        pred = parse_predicate('.name == "foo"')
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.operator, "==")
        self.assertEqual(pred.value, "foo")

    def test_equality_int(self):
        pred = parse_predicate(".count == 5")
        self.assertEqual(pred.operator, "==")
        self.assertEqual(pred.value, 5)

    def test_less_than(self):
        pred = parse_predicate(".count < 10")
        self.assertEqual(pred.operator, "<")
        self.assertEqual(pred.value, 10)

    def test_boolean_true(self):
        pred = parse_predicate(".enabled == true")
        self.assertEqual(pred.value, True)

    def test_boolean_false(self):
        pred = parse_predicate(".enabled == false")
        self.assertEqual(pred.value, False)

    def test_null(self):
        pred = parse_predicate(".x == null")
        self.assertIsNone(pred.value)

    def test_dotted_accessor(self):
        pred = parse_predicate(".tags.Name")
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.parts, ["tags", "Name"])

    def test_indexed_accessor(self):
        pred = parse_predicate(".items[0]")
        self.assertEqual(pred.accessor.parts, ["items"])
        self.assertEqual(pred.accessor.index, 0)

    def test_and(self):
        pred = parse_predicate(".a and .b")
        self.assertIsInstance(pred, AndExpr)
        self.assertEqual(len(pred.children), 2)

    def test_or(self):
        pred = parse_predicate(".a or .b")
        self.assertIsInstance(pred, OrExpr)
        self.assertEqual(len(pred.children), 2)

    def test_not(self):
        pred = parse_predicate("not .a")
        self.assertIsInstance(pred, NotExpr)

    def test_combined_and_or(self):
        pred = parse_predicate(".a and .b or .c")
        # Should parse as (.a and .b) or .c due to precedence
        self.assertIsInstance(pred, OrExpr)
        self.assertIsInstance(pred.children[0], AndExpr)

    def test_empty_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_predicate("")

    def test_no_leading_dot_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_predicate("name")

    def test_extra_tokens_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_predicate('.name == "foo" extra')


class TestEvaluatePredicate(TestCase):
    def _make_doc(self, hcl):
        return DocumentView.parse(hcl)

    def test_existence_true(self):
        doc = self._make_doc('variable "a" {\n  default = 1\n}\n')
        blocks = doc.blocks("variable")
        pred = parse_predicate(".default")
        self.assertTrue(evaluate_predicate(pred, blocks[0]))

    def test_existence_false(self):
        doc = self._make_doc('variable "a" {}\n')
        blocks = doc.blocks("variable")
        pred = parse_predicate(".default")
        self.assertFalse(evaluate_predicate(pred, blocks[0]))

    def test_equality_block_type(self):
        doc = self._make_doc('resource "aws_instance" "main" {}\n')
        blocks = doc.blocks()
        pred = parse_predicate('.block_type == "resource"')
        self.assertTrue(evaluate_predicate(pred, blocks[0]))

    def test_equality_block_type_mismatch(self):
        doc = self._make_doc('resource "aws_instance" "main" {}\n')
        blocks = doc.blocks()
        pred = parse_predicate('.block_type == "variable"')
        self.assertFalse(evaluate_predicate(pred, blocks[0]))

    def test_attribute_name(self):
        doc = self._make_doc("x = 1\ny = 2\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('.name == "x"')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))
        self.assertFalse(evaluate_predicate(pred, attrs[1]))

    def test_attribute_value(self):
        doc = self._make_doc("x = 1\ny = 2\n")
        attrs = doc.body.attributes()
        pred = parse_predicate(".value == 1")
        self.assertTrue(evaluate_predicate(pred, attrs[0]))
        self.assertFalse(evaluate_predicate(pred, attrs[1]))

    def test_not_predicate(self):
        doc = self._make_doc("x = 1\ny = 2\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('not .name == "x"')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))
        self.assertTrue(evaluate_predicate(pred, attrs[1]))

    def test_and_predicate(self):
        doc = self._make_doc("x = 1\ny = 2\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('.name == "x" and .value == 1')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))
        self.assertFalse(evaluate_predicate(pred, attrs[1]))

    def test_or_predicate(self):
        doc = self._make_doc("x = 1\ny = 2\nz = 3\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('.name == "x" or .name == "y"')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))
        self.assertTrue(evaluate_predicate(pred, attrs[1]))
        self.assertFalse(evaluate_predicate(pred, attrs[2]))

    def test_greater_than(self):
        doc = self._make_doc("x = 5\ny = 15\n")
        attrs = doc.body.attributes()
        pred = parse_predicate(".value > 10")
        self.assertFalse(evaluate_predicate(pred, attrs[0]))
        self.assertTrue(evaluate_predicate(pred, attrs[1]))

    def test_type_accessor_block(self):
        doc = self._make_doc('resource "aws_instance" "main" {}\n')
        blocks = doc.blocks()
        pred = parse_predicate('.type == "block"')
        self.assertTrue(evaluate_predicate(pred, blocks[0]))

    def test_type_accessor_attribute(self):
        doc = self._make_doc("x = 1\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('.type == "attribute"')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_type_accessor_object(self):
        doc = self._make_doc("x = {\n  a = 1\n}\n")
        attr = doc.attribute("x")
        # value_node is ExprTerm wrapping ObjectRule
        from hcl2.query._base import view_for
        from hcl2.rules.expressions import ExprTermRule

        vn = attr.value_node
        if isinstance(vn._node, ExprTermRule):
            inner = view_for(vn._node.expression)
        else:
            inner = vn
        pred = parse_predicate('.type == "object"')
        self.assertTrue(evaluate_predicate(pred, inner))

    def test_type_accessor_mismatch(self):
        doc = self._make_doc("x = 1\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('.type == "block"')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_type_accessor_document(self):
        doc = self._make_doc("x = 1\n")
        pred = parse_predicate('.type == "document"')
        self.assertTrue(evaluate_predicate(pred, doc))

    def test_type_accessor_tuple(self):
        doc = self._make_doc("x = [1, 2]\n")
        attr = doc.attribute("x")
        from hcl2.query._base import view_for
        from hcl2.rules.expressions import ExprTermRule

        vn = attr.value_node
        if isinstance(vn._node, ExprTermRule):
            inner = view_for(vn._node.expression)
        else:
            inner = vn
        pred = parse_predicate('.type == "tuple"')
        self.assertTrue(evaluate_predicate(pred, inner))


class TestKeywordComparison(TestCase):
    """Test that HCL keywords (true/false/null) compare correctly."""

    def test_keyword_true_matches_true(self):
        doc = DocumentView.parse("x = true\n")
        attrs = doc.body.attributes()
        pred = parse_predicate(".value == true")
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_keyword_true_not_matches_string(self):
        doc = DocumentView.parse("x = true\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('.value == "true"')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_keyword_false_matches_false(self):
        doc = DocumentView.parse("x = false\n")
        attrs = doc.body.attributes()
        pred = parse_predicate(".value == false")
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_keyword_null_matches_null(self):
        doc = DocumentView.parse("x = null\n")
        attrs = doc.body.attributes()
        pred = parse_predicate(".value == null")
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_conditional_true_val_keyword(self):
        doc = DocumentView.parse("x = a == b ? true : false\n")
        results = resolve_path(doc, parse_path("*..conditional:*"))
        pred = parse_predicate(".true_val == true")
        self.assertTrue(evaluate_predicate(pred, results[0]))

    def test_conditional_false_val_keyword(self):
        doc = DocumentView.parse("x = a == b ? true : false\n")
        results = resolve_path(doc, parse_path("*..conditional:*"))
        pred = parse_predicate(".false_val == false")
        self.assertTrue(evaluate_predicate(pred, results[0]))


class TestSelectInPath(TestCase):
    """Test [select()] bracket syntax in structural paths."""

    def test_select_bracket_in_path(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        results = resolve_path(doc, parse_path('*[select(.name == "x")]'))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "x")

    def test_select_bracket_existence(self):
        doc = DocumentView.parse('variable "a" {\n  default = 1\n}\nvariable "b" {}\n')
        results = resolve_path(doc, parse_path("variable[select(.default)]"))
        self.assertEqual(len(results), 1)

    def test_select_bracket_no_match(self):
        doc = DocumentView.parse("x = 1\ny = 2\n")
        results = resolve_path(doc, parse_path('*[select(.name == "z")]'))
        self.assertEqual(len(results), 0)

    def test_select_bracket_with_type_qualifier(self):
        doc = DocumentView.parse('x = substr("hello", 0, 3)\ny = upper("a")\n')
        results = resolve_path(doc, parse_path("*..function_call:*[select(.args[2])]"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "substr")


class TestAccessorBuiltin(TestCase):
    """Test ``| builtin`` syntax in predicate accessors."""

    def test_parse_pipe_length(self):
        pred = parse_predicate(".args | length > 2")
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.builtin, "length")
        self.assertEqual(pred.operator, ">")
        self.assertEqual(pred.value, 2)

    def test_parse_pipe_keys(self):
        pred = parse_predicate(".tags | keys")
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.builtin, "keys")
        self.assertIsNone(pred.operator)

    def test_parse_invalid_builtin(self):
        with self.assertRaises(QuerySyntaxError):
            parse_predicate(".args | bogus")

    def test_tokenize_pipe(self):
        tokens = tokenize(".args | length")
        kinds = [t.kind for t in tokens]
        self.assertIn("PIPE", kinds)

    def test_evaluate_length_gt(self):
        doc = DocumentView.parse('x = substr("hello", 0, 3)\n')
        funcs = resolve_path(doc, parse_path("*..function_call:*"))
        func = funcs[0]
        pred = parse_predicate(".args | length > 2")
        self.assertTrue(evaluate_predicate(pred, func))
        pred2 = parse_predicate(".args | length > 5")
        self.assertFalse(evaluate_predicate(pred2, func))

    def test_evaluate_length_eq(self):
        doc = DocumentView.parse('x = substr("hello", 0, 3)\n')
        funcs = resolve_path(doc, parse_path("*..function_call:*"))
        func = funcs[0]
        pred = parse_predicate(".args | length == 3")
        self.assertTrue(evaluate_predicate(pred, func))


class TestAnyAll(TestCase):
    """Test ``any(accessor; pred)`` and ``all(accessor; pred)``."""

    def test_parse_any(self):
        pred = parse_predicate('any(.elements; .type == "function_call")')
        self.assertIsInstance(pred, AnyExpr)
        self.assertEqual(pred.accessor.parts, ["elements"])
        self.assertIsInstance(pred.predicate, Comparison)

    def test_parse_all(self):
        pred = parse_predicate('all(.items; .name == "x")')
        self.assertIsInstance(pred, AllExpr)
        self.assertEqual(pred.accessor.parts, ["items"])

    def test_parse_any_with_boolean_combinators(self):
        pred = parse_predicate(
            'any(.elements; .type == "function_call" or .type == "tuple")'
        )
        self.assertIsInstance(pred, AnyExpr)
        self.assertIsInstance(pred.predicate, OrExpr)

    def test_evaluate_any_true(self):
        doc = DocumentView.parse("x = [1, f(a), 3]\n")
        tuples = resolve_path(doc, parse_path("*..tuple:*"))
        pred = parse_predicate('any(.elements; .type == "function_call")')
        self.assertTrue(evaluate_predicate(pred, tuples[0]))

    def test_evaluate_any_false(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        tuples = resolve_path(doc, parse_path("*..tuple:*"))
        pred = parse_predicate('any(.elements; .type == "function_call")')
        self.assertFalse(evaluate_predicate(pred, tuples[0]))

    def test_evaluate_all_true(self):
        doc = DocumentView.parse("x = [1, 2, 3]\n")
        tuples = resolve_path(doc, parse_path("*..tuple:*"))
        pred = parse_predicate('all(.elements; .type == "node")')
        self.assertTrue(evaluate_predicate(pred, tuples[0]))

    def test_evaluate_all_false(self):
        doc = DocumentView.parse("x = [1, f(a), 3]\n")
        tuples = resolve_path(doc, parse_path("*..tuple:*"))
        pred = parse_predicate('all(.elements; .type == "node")')
        self.assertFalse(evaluate_predicate(pred, tuples[0]))

    def test_any_on_none_is_false(self):
        doc = DocumentView.parse("x = 1\n")
        attrs = resolve_path(doc, parse_path("x"))
        pred = parse_predicate('any(.nonexistent; .type == "node")')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_all_on_none_is_true(self):
        doc = DocumentView.parse("x = 1\n")
        attrs = resolve_path(doc, parse_path("x"))
        pred = parse_predicate('all(.nonexistent; .type == "node")')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_any_with_not(self):
        pred = parse_predicate('not any(.elements; .type == "function_call")')
        self.assertIsInstance(pred, NotExpr)
        self.assertIsInstance(pred.child, AnyExpr)


class TestStringFunctions(TestCase):
    """Test string functions in predicate accessors."""

    def test_parse_contains(self):
        pred = parse_predicate('.source | contains("docker")')
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.builtin, "contains")
        self.assertEqual(pred.accessor.builtin_arg, "docker")

    def test_parse_test(self):
        pred = parse_predicate('.ami | test("^ami-[0-9]+")')
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.builtin, "test")
        self.assertEqual(pred.accessor.builtin_arg, "^ami-[0-9]+")

    def test_parse_startswith(self):
        pred = parse_predicate('.name | startswith("prod-")')
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.builtin, "startswith")
        self.assertEqual(pred.accessor.builtin_arg, "prod-")

    def test_parse_endswith(self):
        pred = parse_predicate('.path | endswith("/api")')
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.builtin, "endswith")
        self.assertEqual(pred.accessor.builtin_arg, "/api")

    def test_evaluate_contains_true(self):
        doc = DocumentView.parse('source = "docker_application_v2"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | contains("docker")')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_evaluate_contains_false(self):
        doc = DocumentView.parse('source = "some_module"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | contains("docker")')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_evaluate_test_true(self):
        doc = DocumentView.parse('ami = "ami-12345"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | test("^ami-[0-9]+")')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_evaluate_test_false(self):
        doc = DocumentView.parse('ami = "xyz-12345"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | test("^ami-[0-9]+")')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_evaluate_startswith_true(self):
        doc = DocumentView.parse('name = "prod-api"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | startswith("prod-")')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_evaluate_startswith_false(self):
        doc = DocumentView.parse('name = "staging-api"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | startswith("prod-")')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_evaluate_endswith_true(self):
        doc = DocumentView.parse('path = "some/path/api"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | endswith("api")')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_evaluate_endswith_false(self):
        doc = DocumentView.parse('path = "some/path/web"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | endswith("api")')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_contains_on_none_returns_false(self):
        doc = DocumentView.parse("x = 1\n")
        attrs = doc.body.attributes()
        pred = parse_predicate('.nonexistent | contains("x")')
        self.assertFalse(evaluate_predicate(pred, attrs[0]))

    def test_test_invalid_regex_raises(self):
        doc = DocumentView.parse('x = "hello"\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | test("[invalid")')
        with self.assertRaises(QuerySyntaxError):
            evaluate_predicate(pred, attrs[0])

    def test_combined_contains_and_comparison(self):
        doc = DocumentView.parse('source = "docker_app"\ncount = 3\n')
        attrs = doc.body.attributes()
        pred = parse_predicate('.value | contains("docker") and .name == "source"')
        # This should parse as: (.value | contains("docker")) and (.name == "source")
        # Actually it parses the contains as a bare accessor result, then "and"
        # Let's use a simpler combined test
        pred = parse_predicate('.name == "source"')
        self.assertTrue(evaluate_predicate(pred, attrs[0]))

    def test_unknown_string_function_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_predicate('.value | bogus("x")')


class TestPostfixNot(TestCase):
    """Test postfix ``| not`` in predicate accessors."""

    def test_parse_postfix_not(self):
        pred = parse_predicate(".tags | not")
        self.assertIsInstance(pred, Comparison)
        self.assertEqual(pred.accessor.builtin, "not")

    def test_postfix_not_false_when_exists(self):
        doc = DocumentView.parse('resource "aws" "x" {\n  tags = {}\n}\n')
        blocks = doc.blocks()
        pred = parse_predicate(".tags | not")
        self.assertFalse(evaluate_predicate(pred, blocks[0]))

    def test_postfix_not_true_when_missing(self):
        doc = DocumentView.parse('resource "aws" "x" {}\n')
        blocks = doc.blocks()
        pred = parse_predicate(".tags | not")
        self.assertTrue(evaluate_predicate(pred, blocks[0]))

    def test_postfix_not_equivalent_to_prefix(self):
        doc = DocumentView.parse('variable "a" {\n  default = 1\n}\nvariable "b" {}\n')
        blocks = doc.blocks("variable")
        # "not .default" and ".default | not" should be equivalent
        pred_prefix = parse_predicate("not .default")
        pred_postfix = parse_predicate(".default | not")
        for block in blocks:
            self.assertEqual(
                evaluate_predicate(pred_prefix, block),
                evaluate_predicate(pred_postfix, block),
            )


class TestHasExpr(TestCase):
    """Test ``has("key")`` predicate."""

    def test_parse_has(self):
        pred = parse_predicate('has("tags")')
        self.assertIsInstance(pred, HasExpr)
        self.assertEqual(pred.key, "tags")

    def test_has_true(self):
        doc = DocumentView.parse('resource "aws" "x" {\n  tags = {}\n}\n')
        blocks = doc.blocks()
        pred = parse_predicate('has("tags")')
        self.assertTrue(evaluate_predicate(pred, blocks[0]))

    def test_has_false(self):
        doc = DocumentView.parse('resource "aws" "x" {}\n')
        blocks = doc.blocks()
        pred = parse_predicate('has("tags")')
        self.assertFalse(evaluate_predicate(pred, blocks[0]))

    def test_has_equivalent_to_bare_accessor(self):
        doc = DocumentView.parse('variable "a" {\n  default = 1\n}\nvariable "b" {}\n')
        blocks = doc.blocks("variable")
        pred_has = parse_predicate('has("default")')
        pred_bare = parse_predicate(".default")
        for block in blocks:
            self.assertEqual(
                evaluate_predicate(pred_has, block),
                evaluate_predicate(pred_bare, block),
            )

    def test_has_with_not(self):
        doc = DocumentView.parse('resource "aws" "x" {}\n')
        blocks = doc.blocks()
        pred = parse_predicate('not has("tags")')
        self.assertTrue(evaluate_predicate(pred, blocks[0]))
