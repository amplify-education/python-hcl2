# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.path import QuerySyntaxError
from hcl2.query.pipeline import (
    BuiltinStage,
    ConstructStage,
    PathStage,
    SelectStage,
    classify_stage,
    execute_pipeline,
    split_pipeline,
)


class TestSplitPipeline(TestCase):
    def test_single_stage(self):
        self.assertEqual(split_pipeline("resource"), ["resource"])

    def test_multi_stage(self):
        self.assertEqual(
            split_pipeline("resource[*] | .aws_instance | .tags"),
            ["resource[*]", ".aws_instance", ".tags"],
        )

    def test_bracket_aware(self):
        # Pipe inside brackets should not split
        result = split_pipeline("x[*] | y")
        self.assertEqual(result, ["x[*]", "y"])

    def test_paren_aware(self):
        result = split_pipeline("select(.a | .b) | y")
        # The pipe inside parens should not split
        # Actually this would be select(.a | .b) and y
        # But our grammar doesn't support pipes in predicates,
        # this is just testing depth tracking
        self.assertEqual(len(result), 2)

    def test_quote_aware(self):
        result = split_pipeline('"a | b" | y')
        self.assertEqual(len(result), 2)

    def test_escaped_quote_in_string(self):
        # Escaped quote should not toggle string mode
        result = split_pipeline('"a\\"b | c" | y')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], '"a\\"b | c"')
        self.assertEqual(result[1], "y")

    def test_empty_stage_error(self):
        with self.assertRaises(QuerySyntaxError):
            split_pipeline("x | | y")

    def test_trailing_pipe_error(self):
        with self.assertRaises(QuerySyntaxError):
            split_pipeline("x |")

    def test_leading_pipe_error(self):
        with self.assertRaises(QuerySyntaxError):
            split_pipeline("| x")

    def test_empty_pipeline_error(self):
        with self.assertRaises(QuerySyntaxError):
            split_pipeline("")

    def test_whitespace_stripped(self):
        result = split_pipeline("  x  |  y  ")
        self.assertEqual(result, ["x", "y"])


class TestClassifyStage(TestCase):
    def test_path_stage(self):
        stage = classify_stage("resource.aws_instance")
        self.assertIsInstance(stage, PathStage)
        self.assertEqual(len(stage.segments), 2)

    def test_builtin_keys(self):
        stage = classify_stage("keys")
        self.assertIsInstance(stage, BuiltinStage)
        self.assertEqual(stage.name, "keys")

    def test_builtin_values(self):
        stage = classify_stage("values")
        self.assertIsInstance(stage, BuiltinStage)
        self.assertEqual(stage.name, "values")

    def test_builtin_length(self):
        stage = classify_stage("length")
        self.assertIsInstance(stage, BuiltinStage)
        self.assertEqual(stage.name, "length")

    def test_select_stage(self):
        stage = classify_stage("select(.name)")
        self.assertIsInstance(stage, SelectStage)
        self.assertIsNotNone(stage.predicate)

    def test_select_with_comparison(self):
        stage = classify_stage('select(.name == "foo")')
        self.assertIsInstance(stage, SelectStage)

    def test_path_with_wildcard(self):
        stage = classify_stage("*[*]")
        self.assertIsInstance(stage, PathStage)


class TestExecutePipeline(TestCase):
    def _make_doc(self, hcl):
        return DocumentView.parse(hcl)

    def test_single_stage_identity(self):
        doc = self._make_doc("x = 1\n")
        stage = classify_stage("x")
        results = execute_pipeline(doc, [stage])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "x")

    def test_multi_stage_chaining(self):
        doc = self._make_doc('resource "aws_instance" "main" {\n  ami = "test"\n}\n')
        # Pipe unwraps blocks to body, so chain with body attributes
        stages = [
            classify_stage(s)
            for s in split_pipeline("resource.aws_instance.main | .ami")
        ]
        results = execute_pipeline(doc, stages)
        self.assertEqual(len(results), 1)

    def test_empty_intermediate(self):
        doc = self._make_doc("x = 1\n")
        stages = [classify_stage(s) for s in split_pipeline("nonexistent | .foo")]
        results = execute_pipeline(doc, stages)
        self.assertEqual(len(results), 0)

    def test_pipe_with_wildcard(self):
        doc = self._make_doc("x = 1\ny = 2\nz = 3\n")
        stages = [classify_stage(s) for s in split_pipeline("*[*] | length")]
        results = execute_pipeline(doc, stages)
        self.assertEqual(len(results), 3)
        # Each attribute has length 1
        self.assertEqual(results, [1, 1, 1])

    def test_pipe_builtin(self):
        doc = self._make_doc("x = {\n  a = 1\n  b = 2\n}\n")
        stages = [classify_stage(s) for s in split_pipeline("x | keys")]
        results = execute_pipeline(doc, stages)
        self.assertEqual(len(results), 1)
        self.assertEqual(sorted(results[0]), ["a", "b"])

    def test_pipe_select(self):
        doc = self._make_doc('variable "a" {\n  default = 1\n}\nvariable "b" {}\n')
        stages = [
            classify_stage(s) for s in split_pipeline("variable[*] | select(.default)")
        ]
        results = execute_pipeline(doc, stages)
        self.assertEqual(len(results), 1)

    def test_backward_compat_no_pipe(self):
        """Single structural path still works through pipeline."""
        doc = self._make_doc('resource "aws_instance" "main" {\n  ami = "test"\n}\n')
        stages = [classify_stage("resource.aws_instance.main.ami")]
        results = execute_pipeline(doc, stages)
        self.assertEqual(len(results), 1)


class TestPropertyAccessPipeStages(TestCase):
    """Test property accessor pipe stages (Option B)."""

    def _run(self, hcl, query):
        doc = DocumentView.parse(hcl)
        stages = [classify_stage(s) for s in split_pipeline(query)]
        return execute_pipeline(doc, stages)

    def test_block_type_property(self):
        r = self._run(
            'resource "aws" "x" {\n  ami = 1\n}\n',
            "resource[*] | .block_type",
        )
        self.assertEqual(r, ["resource"])

    def test_name_labels_property(self):
        r = self._run(
            'resource "aws" "x" {\n  ami = 1\n}\n',
            "resource[*] | .name_labels",
        )
        self.assertEqual(r, [["aws", "x"]])

    def test_labels_property(self):
        r = self._run(
            'resource "aws" "x" {\n  ami = 1\n}\n',
            "resource[*] | .labels",
        )
        self.assertEqual(r, [["resource", "aws", "x"]])

    def test_attribute_name_property(self):
        r = self._run("x = 1\ny = 2\n", "*[*] | .name")
        self.assertEqual(sorted(r), ["x", "y"])

    def test_function_call_name_property(self):
        r = self._run(
            'x = substr("hello", 0, 3)\n',
            "*..function_call:*[*] | .name",
        )
        self.assertEqual(r, ["substr"])

    def test_property_then_builtin(self):
        """Property access result feeds into a builtin."""
        r = self._run(
            'resource "aws" "x" {\n  ami = 1\n}\n',
            "resource[*] | .labels | length",
        )
        self.assertEqual(r, [3])

    def test_structural_still_works_after_pipe(self):
        """Structural path resolution still works through pipes."""
        r = self._run(
            'resource "aws" "x" {\n  ami = "test"\n}\n',
            "resource.aws.x | .ami",
        )
        self.assertEqual(len(r), 1)

    def test_type_qualifier_filter_in_pipe(self):
        """Type qualifier in pipe stage filters by value type."""
        r = self._run(
            "a = {x = 1}\nb = [1, 2]\nc = 3\n",
            "*[*] | object:*",
        )
        self.assertEqual(len(r), 1)
        self.assertEqual(type(r[0]).__name__, "ObjectView")

    def test_type_qualifier_tuple_in_pipe(self):
        r = self._run(
            "a = {x = 1}\nb = [1, 2]\nc = 3\n",
            "*[*] | tuple:*",
        )
        self.assertEqual(len(r), 1)
        self.assertEqual(type(r[0]).__name__, "TupleView")


class TestOptionalTolerance(TestCase):
    """Test that trailing ? is tolerated in pipeline stages."""

    def test_classify_stage_optional(self):
        stage = classify_stage("resource?")
        self.assertIsInstance(stage, PathStage)

    def test_classify_stage_optional_with_bracket(self):
        stage = classify_stage("x[*]?")
        self.assertIsInstance(stage, PathStage)
        self.assertTrue(stage.segments[0].select_all)

    def test_classify_builtin_optional(self):
        stage = classify_stage("keys?")
        self.assertIsInstance(stage, BuiltinStage)
        self.assertEqual(stage.name, "keys")

    def test_classify_select_optional(self):
        stage = classify_stage("select(.name)?")
        # select(.name)? — ? stripped first, then select() detected
        self.assertIsInstance(stage, SelectStage)

    def test_brace_aware_split(self):
        """Pipes inside braces should not split."""
        result = split_pipeline("x[*] | {source, cpu}")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1], "{source, cpu}")


class TestConstructStage(TestCase):
    """Test object construction ``{field1, field2}`` pipeline stage."""

    def _run(self, hcl, query):
        doc = DocumentView.parse(hcl)
        stages = [classify_stage(s) for s in split_pipeline(query)]
        return execute_pipeline(doc, stages)

    def test_classify_construct(self):
        stage = classify_stage("{source, cpu}")
        self.assertIsInstance(stage, ConstructStage)
        self.assertEqual(len(stage.fields), 2)
        self.assertEqual(stage.fields[0][0], "source")
        self.assertEqual(stage.fields[1][0], "cpu")

    def test_classify_construct_renamed(self):
        stage = classify_stage("{mod: .source, vcpu: .cpu}")
        self.assertIsInstance(stage, ConstructStage)
        self.assertEqual(stage.fields[0][0], "mod")
        self.assertEqual(stage.fields[1][0], "vcpu")

    def test_execute_construct_shorthand(self):
        r = self._run(
            'resource "aws" "x" {\n  ami = "test"\n  count = 2\n}\n',
            "resource.aws.x | {ami, count}",
        )
        self.assertEqual(len(r), 1)
        self.assertIsInstance(r[0], dict)
        self.assertIn("ami", r[0])
        self.assertIn("count", r[0])
        # Values should be flat, not nested dicts like {"ami": {"ami": ...}}
        self.assertNotIsInstance(r[0]["ami"], dict)
        self.assertEqual(r[0]["ami"], '"test"')
        self.assertEqual(r[0]["count"], 2)

    def test_execute_construct_renamed(self):
        r = self._run(
            'resource "aws" "x" {\n  ami = "test"\n}\n',
            "resource[*] | {type: .block_type, name: .name_labels}",
        )
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["type"], "resource")
        self.assertEqual(r[0]["name"], ["aws", "x"])

    def test_construct_missing_field(self):
        r = self._run(
            "x = 1\n",
            "x | {value, nonexistent}",
        )
        self.assertEqual(len(r), 1)
        self.assertIsNone(r[0]["nonexistent"])

    def test_construct_with_select(self):
        r = self._run(
            "a = 1\nb = 2\nc = 3\n",
            "*[select(.value > 1)] | {name, value}",
        )
        self.assertEqual(len(r), 2)
        names = sorted(d["name"] for d in r)
        self.assertEqual(names, ["b", "c"])

    def test_construct_with_index(self):
        stage = classify_stage("{first: .items[0]}")
        self.assertIsInstance(stage, ConstructStage)
        self.assertEqual(stage.fields[0][0], "first")
