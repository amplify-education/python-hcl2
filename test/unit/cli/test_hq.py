# pylint: disable=C0103,C0114,C0115,C0116
import json
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from cli.hq import _dispatch_query, _normalize_eval_expr, main
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


class TestHqMainCli(TestCase):
    def test_main_structural(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tf", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            try:
                with patch("sys.argv", ["hq", "x", f.name, "--value"]):
                    with patch("sys.stdout", new_callable=StringIO) as mock_out:
                        with self.assertRaises(SystemExit) as cm:
                            from cli.hq import main

                            main()
                        self.assertEqual(cm.exception.code, 0)
                        self.assertIn("1", mock_out.getvalue())
            finally:
                os.unlink(f.name)

    def test_main_schema(self):
        with patch("sys.argv", ["hq", "--schema"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                with self.assertRaises(SystemExit) as cm:
                    from cli.hq import main

                    main()
                self.assertEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 1)
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
                        self.assertEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 0)
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
                            self.assertNotEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 0)
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
                        self.assertEqual(cm.exception.code, 0)
                        data = json.loads(mock_out.getvalue())
                        self.assertIsInstance(data, list)
            finally:
                os.unlink(f.name)
