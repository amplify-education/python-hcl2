# pylint: disable=C0103,C0114,C0115,C0116,C0302
import json
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from cli.hq import (
    EXIT_IO_ERROR,
    EXIT_NO_RESULTS,
    EXIT_PARSE_ERROR,
    EXIT_QUERY_ERROR,
    EXIT_SUCCESS,
    _dispatch_query,
    _expand_file_args,
    _normalize_eval_expr,
    _process_file,
    main,
)
from hcl2.query.body import DocumentView


class TestNormalizeEvalExpr(TestCase):
    def test_explicit_underscore(self):
        self.assertEqual(_normalize_eval_expr("_.foo"), "_.foo")

    def test_dot_prefix(self):
        self.assertEqual(_normalize_eval_expr(".foo"), "_.foo")

    def test_bare_property(self):
        self.assertEqual(_normalize_eval_expr("name_labels"), "_.name_labels")

    def test_builtin_call(self):
        self.assertEqual(_normalize_eval_expr("len(_.x)"), "len(_.x)")

    def test_doc_ref(self):
        self.assertEqual(_normalize_eval_expr("doc.blocks()"), "doc.blocks()")

    def test_empty(self):
        self.assertEqual(_normalize_eval_expr(""), "_")


class TestDispatchQuery(TestCase):
    def _make_doc(self, hcl):
        return DocumentView.parse(hcl)

    def test_structural(self):
        doc = self._make_doc("x = 1\n")
        results = _dispatch_query("x", False, doc)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "x")

    def test_eval(self):
        doc = self._make_doc("x = 1\n")
        results = _dispatch_query('doc.attribute("x").value', True, doc)
        self.assertEqual(results, [1])

    def test_hybrid(self):
        doc = self._make_doc('variable "a" {}\nvariable "b" {}\n')
        results = _dispatch_query("variable[*]::block_type", False, doc)
        self.assertEqual(results, ["variable", "variable"])

    def test_hybrid_name_labels(self):
        doc = self._make_doc('variable "a" {}\nvariable "b" {}\n')
        results = _dispatch_query("variable[*]::name_labels", False, doc)
        self.assertEqual(results, [["a"], ["b"]])

    def test_pipe(self):
        doc = self._make_doc('resource "aws_instance" "main" {\n  ami = "test"\n}\n')
        # Pipe splits at body boundaries; label traversal stays in one stage
        results = _dispatch_query("resource.aws_instance.main | .ami", False, doc)
        self.assertEqual(len(results), 1)

    def test_pipe_with_builtin(self):
        doc = self._make_doc("x = {\n  a = 1\n  b = 2\n}\n")
        results = _dispatch_query("x | keys", False, doc)
        self.assertEqual(len(results), 1)
        self.assertEqual(sorted(results[0]), ["a", "b"])

    def test_pipe_with_select(self):
        doc = self._make_doc('variable "a" {\n  default = 1\n}\nvariable "b" {}\n')
        results = _dispatch_query("variable[*] | select(.default)", False, doc)
        self.assertEqual(len(results), 1)

    def test_pipe_with_length(self):
        doc = self._make_doc("x = [1, 2, 3]\n")
        results = _dispatch_query("x | length", False, doc)
        self.assertEqual(results, [3])


class TestExpandFileArgs(TestCase):
    def test_stdin_passthrough(self):
        self.assertEqual(_expand_file_args(["-"]), ["-"])

    def test_literal_passthrough(self):
        self.assertEqual(_expand_file_args(["foo.tf"]), ["foo.tf"])

    def test_glob_expansion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("a.tf", "b.tf", "c.json"):
                with open(os.path.join(tmpdir, name), "w", encoding="utf-8"):
                    pass
            pattern = os.path.join(tmpdir, "*.tf")
            result = _expand_file_args([pattern])
            self.assertEqual(len(result), 2)
            self.assertTrue(all(r.endswith(".tf") for r in result))

    def test_glob_no_match_keeps_literal(self):
        result = _expand_file_args(["/nonexistent/path/*.tf"])
        self.assertEqual(result, ["/nonexistent/path/*.tf"])

    def test_recursive_glob(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub")
            os.makedirs(subdir)
            with open(os.path.join(tmpdir, "a.tf"), "w", encoding="utf-8"):
                pass
            with open(os.path.join(subdir, "b.tf"), "w", encoding="utf-8"):
                pass
            pattern = os.path.join(tmpdir, "**", "*.tf")
            result = _expand_file_args([pattern])
            self.assertEqual(len(result), 2)


class TestHqMainCli(TestCase):
    def test_main_structural(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--value"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        self.assertIn("1", mock_out.getvalue())
            finally:
                os.unlink(f.name)

    def test_main_schema(self):
        with patch("sys.argv", ["hq", "--schema"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                data = json.loads(mock_out.getvalue())
                self.assertIn("views", data)

    def test_main_no_results_exits_1(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "nonexistent", f.name]):
                    with patch("sys.stdout", new_callable=StringIO):
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_NO_RESULTS)
            finally:
                os.unlink(f.name)

    def test_optional_no_results_exits_0(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "nonexistent?", f.name, "--value"]):
                    with patch("sys.stdout", new_callable=StringIO):
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
            finally:
                os.unlink(f.name)

    def test_optional_with_results(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x?", f.name, "--value"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        self.assertIn("1", mock_out.getvalue())
            finally:
                os.unlink(f.name)

    def test_optional_not_stripped_in_eval(self):
        """? is valid Python syntax, should not be stripped in eval mode."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                # This should fail as "x?" is not valid Python, but the ?
                # should NOT be stripped since we're in eval mode
                with patch("sys.argv", ["hq", "-e", "x?", f.name]):
                    with patch("sys.stdout", new_callable=StringIO):
                        with patch("sys.stderr", new_callable=StringIO):
                            with self.assertRaises(SystemExit) as cm:
                                main()
                            # Should fail (bad Python), not silently succeed
                            self.assertNotEqual(cm.exception.code, EXIT_SUCCESS)
            finally:
                os.unlink(f.name)

    def test_raw_strips_string_quotes(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write('ami = "test-123"\n')
            f.flush()
            try:
                with patch("sys.argv", ["hq", "ami", f.name, "--raw"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue().strip()
                        self.assertEqual(output, "test-123")
            finally:
                os.unlink(f.name)

    def test_raw_integer_unchanged(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 42\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--raw"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue().strip()
                        self.assertIn("42", output)
            finally:
                os.unlink(f.name)

    def test_diff_identical_files(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f2:
            f1.write("x = 1\n")
            f2.write("x = 1\n")
            f1.flush()
            f2.flush()
            try:
                # hq --diff FILE2 FILE1 (FILE1 is first positional)
                with patch("sys.argv", ["hq", f1.name, "--diff", f2.name]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        # No output for identical files
                        self.assertEqual(mock_out.getvalue().strip(), "")
            finally:
                os.unlink(f1.name)
                os.unlink(f2.name)

    def test_diff_changed_files(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f2:
            f1.write("x = 1\n")
            f2.write("x = 2\n")
            f1.flush()
            f2.flush()
            try:
                with patch("sys.argv", ["hq", f1.name, "--diff", f2.name]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_NO_RESULTS)
                        output = mock_out.getvalue().strip()
                        self.assertIn("~", output)
            finally:
                os.unlink(f1.name)
                os.unlink(f2.name)

    def test_diff_json_output(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f2:
            f1.write("x = 1\ny = 2\n")
            f2.write("x = 1\nz = 3\n")
            f1.flush()
            f2.flush()
            try:
                with patch("sys.argv", ["hq", f1.name, "--diff", f2.name, "--json"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_NO_RESULTS)
                        data = json.loads(mock_out.getvalue())
                        self.assertIsInstance(data, list)
                        self.assertTrue(len(data) > 0)
            finally:
                os.unlink(f1.name)
                os.unlink(f2.name)

    def test_missing_query_with_file_arg_errors(self):
        """When user passes only a file path (no query), error instead of hanging on stdin."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", f.name, "--json"]):
                    with patch("sys.stdin") as mock_stdin:
                        mock_stdin.isatty.return_value = True
                        with patch("sys.stderr", new_callable=StringIO):
                            with self.assertRaises(SystemExit) as cm:
                                main()
                            self.assertEqual(cm.exception.code, 2)
            finally:
                os.unlink(f.name)

    def test_main_pipe_query(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = {\n  a = 1\n  b = 2\n}\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x | keys", f.name, "--json"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        data = json.loads(mock_out.getvalue())
                        self.assertIsInstance(data, list)
            finally:
                os.unlink(f.name)


class TestExitCodes(TestCase):
    """Test distinct exit codes for different error conditions."""

    def test_success_exits_0(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--value"]):
                    with patch("sys.stdout", new_callable=StringIO):
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
            finally:
                os.unlink(f.name)

    def test_no_results_exits_1(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "nonexistent", f.name]):
                    with patch("sys.stdout", new_callable=StringIO):
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_NO_RESULTS)
            finally:
                os.unlink(f.name)

    def test_parse_error_exits_2(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("{invalid hcl content\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name]):
                    with patch("sys.stdout", new_callable=StringIO):
                        with patch("sys.stderr", new_callable=StringIO):
                            with self.assertRaises(SystemExit) as cm:
                                main()
                            self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)
            finally:
                os.unlink(f.name)

    def test_query_syntax_error_exits_3(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "[[[", f.name]):
                    with patch("sys.stdout", new_callable=StringIO):
                        with patch("sys.stderr", new_callable=StringIO):
                            with self.assertRaises(SystemExit) as cm:
                                main()
                            self.assertEqual(cm.exception.code, EXIT_QUERY_ERROR)
            finally:
                os.unlink(f.name)

    def test_io_error_exits_4(self):
        with patch("sys.argv", ["hq", "x", "/nonexistent/file.tf"]):
            with patch("sys.stdout", new_callable=StringIO):
                with patch("sys.stderr", new_callable=StringIO):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_IO_ERROR)

    def test_multi_file_success_masks_parse_error(self):
        """If any file produces results, exit 0 even if others fail."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as good, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as bad:
            good.write("x = 1\n")
            bad.write("{invalid\n")
            good.flush()
            bad.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "x", good.name, bad.name, "--value"],
                ):
                    with patch("sys.stdout", new_callable=StringIO):
                        with patch("sys.stderr", new_callable=StringIO):
                            with self.assertRaises(SystemExit) as cm:
                                main()
                            self.assertEqual(cm.exception.code, EXIT_SUCCESS)
            finally:
                os.unlink(good.name)
                os.unlink(bad.name)

    def test_multi_file_worst_exit_wins(self):
        """When no results, worst error code wins."""
        with patch(
            "sys.argv",
            ["hq", "x", "/nonexistent1.tf", "/nonexistent2.tf"],
        ):
            with patch("sys.stdout", new_callable=StringIO):
                with patch("sys.stderr", new_callable=StringIO):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_IO_ERROR)


class TestMultipleFileArgs(TestCase):
    def test_two_files(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f2:
            f1.write("x = 1\n")
            f2.write("x = 2\n")
            f1.flush()
            f2.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "x", f1.name, f2.name, "--value"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue()
                        # Both files should have output with filename prefix
                        self.assertIn(f1.name, output)
                        self.assertIn(f2.name, output)
            finally:
                os.unlink(f1.name)
                os.unlink(f2.name)

    def test_dir_and_file_mix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tf_path = os.path.join(tmpdir, "a.tf")
            with open(tf_path, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tf", delete=False
            ) as f2:
                f2.write("x = 2\n")
                f2.flush()
                try:
                    with patch(
                        "sys.argv",
                        ["hq", "x", tmpdir, f2.name, "--value"],
                    ):
                        with patch("sys.stdout", new_callable=StringIO) as mock_out:
                            with self.assertRaises(SystemExit) as cm:
                                main()
                            self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                            output = mock_out.getvalue()
                            self.assertIn("1", output)
                            self.assertIn("2", output)
                finally:
                    os.unlink(f2.name)

    def test_stdin_default_when_no_file(self):
        """When no FILE args, defaults to stdin."""
        with patch("sys.argv", ["hq", "x", "--value"]):
            with patch("sys.stdin", StringIO("x = 1\n")):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                    self.assertIn("1", mock_out.getvalue())


class TestGlobExpansion(TestCase):
    def test_glob_pattern_in_file_arg(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ("a.tf", "b.tf"):
                with open(os.path.join(tmpdir, name), "w", encoding="utf-8") as f:
                    f.write("x = 1\n")
            pattern = os.path.join(tmpdir, "*.tf")
            with patch("sys.argv", ["hq", "x", pattern, "--value"]):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                    lines = [
                        line for line in mock_out.getvalue().strip().split("\n") if line
                    ]
                    # Should have results from both files
                    self.assertEqual(len(lines), 2)


class TestCompactJson(TestCase):
    def test_tty_gets_indented(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--json"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        mock_out.isatty = lambda: True
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue()
                        # Indented output has newlines
                        self.assertIn("\n", output.strip())
            finally:
                os.unlink(f.name)

    def test_non_tty_gets_compact(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--json"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        mock_out.isatty = lambda: False
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue().strip()
                        # Compact: single line
                        self.assertEqual(output.count("\n"), 0)
            finally:
                os.unlink(f.name)

    def test_explicit_indent_overrides(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = {\n  a = 1\n}\n")
            f.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "x", f.name, "--json", "--json-indent", "4"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        mock_out.isatty = lambda: False
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue()
                        # Should be indented with 4 spaces
                        self.assertIn("    ", output)
            finally:
                os.unlink(f.name)


class TestNdjson(TestCase):
    def test_single_file_multi_result(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write('variable "a" {}\nvariable "b" {}\n')
            f.flush()
            try:
                with patch("sys.argv", ["hq", "variable[*]", f.name, "--ndjson"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        lines = [
                            l
                            for l in mock_out.getvalue().strip().split("\n")
                            if l.strip()
                        ]
                        self.assertEqual(len(lines), 2)
                        # Each line should be valid JSON
                        for line in lines:
                            json.loads(line)
            finally:
                os.unlink(f.name)

    def test_ndjson_with_value_errors(self):
        with patch("sys.argv", ["hq", "x", "--ndjson", "--value"]):
            with patch("sys.stderr", new_callable=StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 2)  # argparse error

    def test_ndjson_with_raw_errors(self):
        with patch("sys.argv", ["hq", "x", "--ndjson", "--raw"]):
            with patch("sys.stderr", new_callable=StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 2)  # argparse error

    def test_multi_file_ndjson_has_provenance(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f2:
            f1.write("x = 1\n")
            f2.write("x = 2\n")
            f1.flush()
            f2.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "x", f1.name, f2.name, "--ndjson"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        lines = [
                            l
                            for l in mock_out.getvalue().strip().split("\n")
                            if l.strip()
                        ]
                        self.assertEqual(len(lines), 2)
                        d1 = json.loads(lines[0])
                        d2 = json.loads(lines[1])
                        self.assertIn("__file__", d1)
                        self.assertIn("__file__", d2)
            finally:
                os.unlink(f1.name)
                os.unlink(f2.name)


class TestProvenance(TestCase):
    def test_multi_file_json_has_file_key(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f2:
            f1.write("x = 1\n")
            f2.write("x = 2\n")
            f1.flush()
            f2.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "x", f1.name, f2.name, "--ndjson"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        lines = [
                            l
                            for l in mock_out.getvalue().strip().split("\n")
                            if l.strip()
                        ]
                        for line in lines:
                            data = json.loads(line)
                            self.assertIn("__file__", data)
            finally:
                os.unlink(f1.name)
                os.unlink(f2.name)

    def test_multi_file_json_produces_valid_merged_array(self):
        """--json with multiple files must produce a single valid JSON array."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f1, tempfile.NamedTemporaryFile(
            mode="w", suffix=".tf", delete=False
        ) as f2:
            f1.write("x = 1\n")
            f2.write("y = 2\n")
            f1.flush()
            f2.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "*", f1.name, f2.name, "--json"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        raw = mock_out.getvalue().strip()
                        # Must be valid JSON (single array, not concatenated)
                        data = json.loads(raw)
                        self.assertIsInstance(data, list)
                        self.assertEqual(len(data), 2)
                        # Each result should have __file__ provenance
                        for item in data:
                            self.assertIn("__file__", item)
            finally:
                os.unlink(f1.name)
                os.unlink(f2.name)

    def test_single_file_json_no_provenance(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--ndjson"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        data = json.loads(mock_out.getvalue().strip())
                        self.assertNotIn("__file__", data)
            finally:
                os.unlink(f.name)


class TestWithLocation(TestCase):
    def test_with_location_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "x", f.name, "--json", "--with-location"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        mock_out.isatty = lambda: True
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        data = json.loads(mock_out.getvalue())
                        self.assertIn("__file__", data)
                        self.assertIn("__line__", data)
            finally:
                os.unlink(f.name)

    def test_with_location_ndjson(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\ny = 2\n")
            f.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "*[*]", f.name, "--ndjson", "--with-location"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        lines = [
                            l
                            for l in mock_out.getvalue().strip().split("\n")
                            if l.strip()
                        ]
                        self.assertTrue(len(lines) >= 2)
                        for line in lines:
                            data = json.loads(line)
                            self.assertIn("__file__", data)
                            self.assertIn("__line__", data)
            finally:
                os.unlink(f.name)

    def test_with_location_after_construct(self):
        """--with-location preserves line numbers through object construction."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write('resource "aws_instance" "main" {\n  ami = "ami-123"\n}\n')
            f.flush()
            try:
                with patch(
                    "sys.argv",
                    [
                        "hq",
                        "resource[*] | {ami: .ami}",
                        f.name,
                        "--json",
                        "--with-location",
                    ],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        mock_out.isatty = lambda: True
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        data = json.loads(mock_out.getvalue())
                        self.assertIn("__file__", data)
                        self.assertIn("__line__", data)
                        self.assertIn("ami", data)
            finally:
                os.unlink(f.name)

    def test_with_location_requires_json(self):
        with patch("sys.argv", ["hq", "x", "--with-location", "--value"]):
            with patch("sys.stderr", new_callable=StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 2)  # argparse error


class TestWithComments(TestCase):
    def test_with_comments_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("# a comment\nx = 1\n")
            f.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", "x", f.name, "--json", "--with-comments"],
                ):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        mock_out.isatty = lambda: True
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        data = json.loads(mock_out.getvalue())
                        # The exact format depends on SerializationOptions,
                        # but the output should be valid JSON
                        self.assertIsNotNone(data)
            finally:
                os.unlink(f.name)

    def test_with_comments_requires_json(self):
        with patch("sys.argv", ["hq", "x", "--with-comments", "--value"]):
            with patch("sys.stderr", new_callable=StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 2)  # argparse error


class TestValueAutoUnwrap(TestCase):
    def test_attribute_value_unwrapped(self):
        """--value on an attribute should return the inner value, not {key: val}."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write('x = "hello"\n')
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--value"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue().strip()
                        # Should not contain the key wrapper
                        self.assertNotIn("x", output)
                        # Should contain the value
                        self.assertIn("hello", output)
            finally:
                os.unlink(f.name)

    def test_attribute_integer_unwrapped(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("count = 42\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "count", f.name, "--value"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                        output = mock_out.getvalue().strip()
                        self.assertEqual(output, "42")
            finally:
                os.unlink(f.name)


class TestOptionalWithSelect(TestCase):
    def test_optional_after_select(self):
        """? after [select(...)] should work."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\ny = 2\n")
            f.flush()
            try:
                with patch(
                    "sys.argv",
                    ["hq", '*[select(.name == "nonexistent")]?', f.name, "--value"],
                ):
                    with patch("sys.stdout", new_callable=StringIO):
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_SUCCESS)
            finally:
                os.unlink(f.name)


class TestProcessFile(TestCase):
    """Unit tests for the _process_file worker function."""

    def test_success(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                args = (f.name, "x", False, "x", False, False, False, True, True, False)
                _fp, code, converted, err = _process_file(args)
                self.assertEqual(code, EXIT_SUCCESS)
                self.assertIsNone(err)
                self.assertEqual(len(converted), 1)
                self.assertIn("__file__", converted[0])
            finally:
                os.unlink(f.name)

    def test_io_error(self):
        args = (
            "/nonexistent.tf",
            "x",
            False,
            "x",
            False,
            False,
            False,
            True,
            True,
            False,
        )
        _fp, code, _converted, err = _process_file(args)
        self.assertEqual(code, EXIT_IO_ERROR)
        self.assertIsNotNone(err)
        self.assertIsNone(_converted)

    def test_parse_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("{invalid\n")
            f.flush()
            try:
                args = (
                    f.name,
                    "x",
                    False,
                    "x",
                    False,
                    False,
                    False,
                    True,
                    True,
                    False,
                )
                _fp, code, _converted, err = _process_file(args)
                self.assertEqual(code, EXIT_PARSE_ERROR)
                self.assertIsNotNone(err)
            finally:
                os.unlink(f.name)

    def test_no_results(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                args = (
                    f.name,
                    "nonexistent",
                    False,
                    "nonexistent",
                    False,
                    False,
                    False,
                    True,
                    True,
                    False,
                )
                _fp, code, converted, err = _process_file(args)
                self.assertEqual(code, EXIT_SUCCESS)
                self.assertEqual(converted, [])
                self.assertIsNone(err)
            finally:
                os.unlink(f.name)


class TestParallelMode(TestCase):
    """Integration tests for --jobs parallel mode."""

    def _make_files(self, tmpdir, count):
        """Create count .tf files with x = N."""
        paths = []
        for i in range(count):
            path = os.path.join(tmpdir, f"f{i:03d}.tf")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"x = {i}\n")
            paths.append(path)
        return paths

    def test_parallel_json_merged(self):
        """Parallel JSON mode produces a valid merged array."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._make_files(tmpdir, 25)
            argv = ["hq", "x"] + paths + ["--json", "--json-indent", "0"]
            with patch("sys.argv", argv):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    mock_out.isatty = lambda: False
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                    data = json.loads(mock_out.getvalue())
                    self.assertIsInstance(data, list)
                    self.assertEqual(len(data), 25)
                    # Each should have __file__ provenance
                    for item in data:
                        self.assertIn("__file__", item)

    def test_parallel_ndjson(self):
        """Parallel NDJSON mode produces valid per-line JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._make_files(tmpdir, 25)
            argv = ["hq", "x"] + paths + ["--ndjson"]
            with patch("sys.argv", argv):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                    lines = [
                        l for l in mock_out.getvalue().strip().split("\n") if l.strip()
                    ]
                    self.assertEqual(len(lines), 25)
                    for line in lines:
                        data = json.loads(line)
                        self.assertIn("__file__", data)

    def test_serial_fallback_with_jobs_0(self):
        """--jobs 0 forces serial even with many files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._make_files(tmpdir, 25)
            argv = ["hq", "x"] + paths + ["--json", "--json-indent", "0", "--jobs", "0"]
            with patch("sys.argv", argv):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    mock_out.isatty = lambda: False
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                    data = json.loads(mock_out.getvalue())
                    self.assertEqual(len(data), 25)

    def test_serial_for_few_files(self):
        """< 20 files stays serial (no pool overhead)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._make_files(tmpdir, 5)
            argv = ["hq", "x"] + paths + ["--json", "--json-indent", "0"]
            with patch("sys.argv", argv):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    mock_out.isatty = lambda: False
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                    data = json.loads(mock_out.getvalue())
                    self.assertEqual(len(data), 5)

    def test_serial_for_value_mode(self):
        """--value mode stays serial even with many files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self._make_files(tmpdir, 25)
            argv = ["hq", "x"] + paths + ["--value"]
            with patch("sys.argv", argv):
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_SUCCESS)
                    lines = [
                        l for l in mock_out.getvalue().strip().split("\n") if l.strip()
                    ]
                    self.assertEqual(len(lines), 25)
