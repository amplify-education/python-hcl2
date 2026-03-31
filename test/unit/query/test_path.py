# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.path import PathSegment, QuerySyntaxError, parse_path


class TestParsePath(TestCase):
    def test_simple(self):
        segments = parse_path("resource")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0], PathSegment("resource", False, None))

    def test_dotted(self):
        segments = parse_path("resource.aws_instance.main")
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].name, "resource")
        self.assertEqual(segments[1].name, "aws_instance")
        self.assertEqual(segments[2].name, "main")

    def test_wildcard(self):
        segments = parse_path("*")
        self.assertEqual(segments[0], PathSegment("*", False, None))

    def test_select_all(self):
        segments = parse_path("variable[*]")
        self.assertEqual(segments[0], PathSegment("variable", True, None))

    def test_index(self):
        segments = parse_path("variable[0]")
        self.assertEqual(segments[0], PathSegment("variable", False, 0))

    def test_complex(self):
        segments = parse_path("resource.aws_instance[*].tags")
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].name, "resource")
        self.assertTrue(segments[1].select_all)
        self.assertEqual(segments[2].name, "tags")

    def test_empty_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_path("")

    def test_recursive_descent(self):
        segments = parse_path("a..b")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0], PathSegment("a", False, None))
        self.assertEqual(segments[1], PathSegment("b", False, None, recursive=True))

    def test_recursive_with_index(self):
        segments = parse_path("resource..tags[*]")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1].name, "tags")
        self.assertTrue(segments[1].recursive)
        self.assertTrue(segments[1].select_all)

    def test_recursive_in_middle(self):
        segments = parse_path("a.b..c.d")
        self.assertEqual(len(segments), 4)
        self.assertFalse(segments[0].recursive)
        self.assertFalse(segments[1].recursive)
        self.assertTrue(segments[2].recursive)
        self.assertFalse(segments[3].recursive)

    def test_triple_dot_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_path("a...b")

    def test_recursive_at_end_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_path("a..")

    def test_leading_dot_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_path(".a")

    def test_invalid_segment_raises(self):
        with self.assertRaises(QuerySyntaxError):
            parse_path("123invalid")

    def test_hyphen_in_name(self):
        segments = parse_path("local-exec")
        self.assertEqual(segments[0].name, "local-exec")

    def test_index_large(self):
        segments = parse_path("items[42]")
        self.assertEqual(segments[0].index, 42)

    def test_type_filter(self):
        segments = parse_path("function_call:length")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].name, "length")
        self.assertEqual(segments[0].type_filter, "function_call")

    def test_type_filter_with_index(self):
        segments = parse_path("function_call:length[0]")
        self.assertEqual(segments[0].name, "length")
        self.assertEqual(segments[0].type_filter, "function_call")
        self.assertEqual(segments[0].index, 0)

    def test_type_filter_with_wildcard(self):
        segments = parse_path("function_call:*[*]")
        self.assertEqual(segments[0].name, "*")
        self.assertEqual(segments[0].type_filter, "function_call")
        self.assertTrue(segments[0].select_all)

    def test_type_filter_in_recursive(self):
        segments = parse_path("*..function_call:length")
        self.assertEqual(len(segments), 2)
        self.assertTrue(segments[1].recursive)
        self.assertEqual(segments[1].type_filter, "function_call")
        self.assertEqual(segments[1].name, "length")

    def test_no_type_filter(self):
        segments = parse_path("length")
        self.assertIsNone(segments[0].type_filter)

    def test_skip_labels(self):
        segments = parse_path("block~")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].name, "block")
        self.assertTrue(segments[0].skip_labels)

    def test_skip_labels_with_bracket(self):
        segments = parse_path("resource~[*]")
        self.assertEqual(segments[0].name, "resource")
        self.assertTrue(segments[0].skip_labels)
        self.assertTrue(segments[0].select_all)

    def test_skip_labels_with_select(self):
        segments = parse_path("block~[select(.ami)]")
        self.assertEqual(segments[0].name, "block")
        self.assertTrue(segments[0].skip_labels)
        self.assertIsNotNone(segments[0].predicate)

    def test_skip_labels_in_path(self):
        segments = parse_path("block~.ami")
        self.assertEqual(len(segments), 2)
        self.assertTrue(segments[0].skip_labels)
        self.assertFalse(segments[1].skip_labels)

    def test_no_skip_labels_by_default(self):
        segments = parse_path("block")
        self.assertFalse(segments[0].skip_labels)

    def test_select_with_trailing_star(self):
        segments = parse_path("variable[select(.default)][*]")
        self.assertEqual(segments[0].name, "variable")
        self.assertIsNotNone(segments[0].predicate)
        self.assertTrue(segments[0].select_all)
        self.assertIsNone(segments[0].index)

    def test_select_with_trailing_index(self):
        segments = parse_path("variable[select(.default)][0]")
        self.assertEqual(segments[0].name, "variable")
        self.assertIsNotNone(segments[0].predicate)
        self.assertFalse(segments[0].select_all)
        self.assertEqual(segments[0].index, 0)

    def test_select_no_trailing_bracket(self):
        segments = parse_path("variable[select(.default)]")
        self.assertIsNotNone(segments[0].predicate)
        self.assertTrue(segments[0].select_all)
        self.assertIsNone(segments[0].index)

    def test_optional_suffix(self):
        segments = parse_path("x?")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].name, "x")

    def test_optional_with_bracket(self):
        segments = parse_path("x[*]?")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].name, "x")
        self.assertTrue(segments[0].select_all)

    def test_optional_after_select(self):
        segments = parse_path("*[select(.x)]?")
        self.assertEqual(len(segments), 1)
        self.assertIsNotNone(segments[0].predicate)

    def test_optional_produces_same_as_without(self):
        seg_plain = parse_path("resource")
        seg_opt = parse_path("resource?")
        self.assertEqual(seg_plain[0].name, seg_opt[0].name)
        self.assertEqual(seg_plain[0].select_all, seg_opt[0].select_all)

    def test_escaped_quote_in_string(self):
        # Escaped quote inside a quoted string should not terminate it
        segments = parse_path('*[select(.name == "a\\"b")]')
        self.assertEqual(len(segments), 1)
        self.assertIsNotNone(segments[0].predicate)
