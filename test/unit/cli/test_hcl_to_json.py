# pylint: disable=C0103,C0114,C0115,C0116
import json
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from cli.helpers import EXIT_IO_ERROR, EXIT_PARSE_ERROR, EXIT_PARTIAL
from cli.hcl_to_json import main


SIMPLE_HCL = "x = 1\n"
SIMPLE_JSON_DICT = {"x": 1}


def _write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestHclToJson(TestCase):
    def test_single_file_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, SIMPLE_HCL)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", hcl_path]):
                with patch("sys.stdout", stdout):
                    main()

            result = json.loads(stdout.getvalue())
            self.assertEqual(result["x"], 1)

    def test_single_file_to_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            out_path = os.path.join(tmpdir, "test.json")
            _write_file(hcl_path, SIMPLE_HCL)

            with patch("sys.argv", ["hcl2tojson", hcl_path, "-o", out_path]):
                main()

            result = json.loads(_read_file(out_path))
            self.assertEqual(result["x"], 1)

    def test_single_file_to_stdout_single_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, SIMPLE_HCL)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", hcl_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertTrue(output.endswith("\n"), "output should end with newline")
            self.assertFalse(
                output.endswith("\n\n"),
                "output should not have double trailing newline",
            )

    def test_stdin(self):
        stdout = StringIO()
        stdin = StringIO(SIMPLE_HCL)
        with patch("sys.argv", ["hcl2tojson", "-"]):
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                main()

        result = json.loads(stdout.getvalue())
        self.assertEqual(result["x"], 1)

    def test_stdin_single_trailing_newline(self):
        stdout = StringIO()
        stdin = StringIO(SIMPLE_HCL)
        with patch("sys.argv", ["hcl2tojson", "-"]):
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                main()

        output = stdout.getvalue()
        self.assertTrue(output.endswith("\n"), "output should end with newline")
        self.assertFalse(
            output.endswith("\n\n"), "output should not have double trailing newline"
        )

    def test_directory_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "a.tf"), SIMPLE_HCL)
            _write_file(os.path.join(in_dir, "b.hcl"), SIMPLE_HCL)
            _write_file(os.path.join(in_dir, "readme.txt"), "not hcl")

            with patch("sys.argv", ["hcl2tojson", in_dir, "-o", out_dir]):
                main()

            self.assertTrue(os.path.exists(os.path.join(out_dir, "a.json")))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "b.json")))
            self.assertFalse(os.path.exists(os.path.join(out_dir, "readme.json")))

            result = json.loads(_read_file(os.path.join(out_dir, "a.json")))
            self.assertEqual(result["x"], 1)

    def test_with_meta_flag(self):
        hcl_block = 'resource "a" "b" {\n  x = 1\n}\n'
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, hcl_block)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--with-meta", hcl_path]):
                with patch("sys.stdout", stdout):
                    main()

            result = json.loads(stdout.getvalue())
            self.assertIn("resource", result)

    def test_no_comments_flag(self):
        hcl_with_comment = "# a comment\nx = 1\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, hcl_with_comment)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--with-comments", hcl_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn("comment", output)

    def test_wrap_objects_flag(self):
        hcl_input = "x = {\n  a = 1\n}\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, hcl_input)

            stdout_default = StringIO()
            stdout_wrapped = StringIO()
            with patch("sys.argv", ["hcl2tojson", hcl_path]):
                with patch("sys.stdout", stdout_default):
                    main()
            with patch("sys.argv", ["hcl2tojson", "--wrap-objects", hcl_path]):
                with patch("sys.stdout", stdout_wrapped):
                    main()

            default = json.loads(stdout_default.getvalue())
            wrapped = json.loads(stdout_wrapped.getvalue())
            self.assertNotEqual(default["x"], wrapped["x"])

    def test_wrap_tuples_flag(self):
        hcl_input = "x = [1, 2]\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, hcl_input)

            stdout_default = StringIO()
            stdout_wrapped = StringIO()
            with patch("sys.argv", ["hcl2tojson", hcl_path]):
                with patch("sys.stdout", stdout_default):
                    main()
            with patch("sys.argv", ["hcl2tojson", "--wrap-tuples", hcl_path]):
                with patch("sys.stdout", stdout_wrapped):
                    main()

            default = json.loads(stdout_default.getvalue())
            wrapped = json.loads(stdout_wrapped.getvalue())
            self.assertNotEqual(default["x"], wrapped["x"])

    def test_skip_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "good.tf"), SIMPLE_HCL)
            _write_file(os.path.join(in_dir, "bad.tf"), "this is {{{{ not valid hcl")

            with patch("sys.argv", ["hcl2tojson", "-s", in_dir, "-o", out_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARTIAL)

            self.assertTrue(os.path.exists(os.path.join(out_dir, "good.json")))

    def test_directory_to_stdout_without_ndjson_errors(self):
        """Directory without -o or --ndjson is an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            os.mkdir(in_dir)
            _write_file(os.path.join(in_dir, "a.tf"), "a = 1\n")
            _write_file(os.path.join(in_dir, "b.tf"), "b = 2\n")

            with patch("sys.argv", ["hcl2tojson", in_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 2)

    def test_stdin_default_when_no_args(self):
        """No PATH args reads from stdin (like jq)."""
        stdout = StringIO()
        stdin = StringIO(SIMPLE_HCL)
        with patch("sys.argv", ["hcl2tojson"]):
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                main()

        result = json.loads(stdout.getvalue())
        self.assertEqual(result["x"], 1)

    def test_multiple_files_to_stdout_without_ndjson_errors(self):
        """Multiple files without -o or --ndjson is an error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.tf")
            path_b = os.path.join(tmpdir, "b.tf")
            _write_file(path_a, "a = 1\n")
            _write_file(path_b, "b = 2\n")

            with patch("sys.argv", ["hcl2tojson", path_a, path_b]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 2)

    def test_multiple_files_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.tf")
            path_b = os.path.join(tmpdir, "b.tf")
            out_dir = os.path.join(tmpdir, "out")
            _write_file(path_a, "a = 1\n")
            _write_file(path_b, "b = 2\n")

            with patch("sys.argv", ["hcl2tojson", path_a, path_b, "-o", out_dir]):
                main()

            self.assertTrue(os.path.exists(os.path.join(out_dir, "a.json")))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "b.json")))

    def test_multiple_files_invalid_path_exits_4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.tf")
            out_dir = os.path.join(tmpdir, "out")
            os.mkdir(out_dir)
            _write_file(path_a, "a = 1\n")

            with patch(
                "sys.argv",
                ["hcl2tojson", path_a, "/nonexistent.tf", "-o", out_dir],
            ):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_IO_ERROR)

    def test_invalid_path_exits_4(self):
        with patch("sys.argv", ["hcl2tojson", "/nonexistent/path/foo.tf"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, EXIT_IO_ERROR)


class TestSingleFileErrorHandling(TestCase):
    def test_skip_error_with_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.tf")
            out_path = os.path.join(tmpdir, "out.json")
            _write_file(in_path, "this is {{{{ not valid hcl")

            with patch("sys.argv", ["hcl2tojson", "-s", in_path, "-o", out_path]):
                main()

            # The partial output file is cleaned up on skipped errors.
            self.assertFalse(os.path.exists(out_path))

    def test_parse_error_exits_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.tf")
            out_path = os.path.join(tmpdir, "out.json")
            _write_file(in_path, "this is {{{{ not valid hcl")

            with patch("sys.argv", ["hcl2tojson", in_path, "-o", out_path]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)

    def test_skip_error_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.tf")
            _write_file(in_path, "this is {{{{ not valid hcl")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "-s", in_path]):
                with patch("sys.stdout", stdout):
                    main()

            self.assertEqual(stdout.getvalue(), "")

    def test_parse_error_to_stdout_exits_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.tf")
            _write_file(in_path, "this is {{{{ not valid hcl")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", in_path]):
                with patch("sys.stdout", stdout):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)


class TestHclToJsonFlags(TestCase):
    def _run_hcl_to_json(self, hcl_content, extra_flags=None):
        """Helper: write HCL to a temp file, run main() with flags, return parsed JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, hcl_content)

            stdout = StringIO()
            argv = ["hcl2tojson"] + (extra_flags or []) + [hcl_path]
            with patch("sys.argv", argv):
                with patch("sys.stdout", stdout):
                    main()
            return json.loads(stdout.getvalue())

    def test_no_explicit_blocks_flag(self):
        hcl = 'resource "a" "b" {\n  x = 1\n}\n'
        default = self._run_hcl_to_json(hcl)
        no_blocks = self._run_hcl_to_json(hcl, ["--no-explicit-blocks"])
        # With explicit blocks, the value is wrapped in a list; without, it may differ
        self.assertNotEqual(default, no_blocks)

    def test_no_preserve_heredocs_flag(self):
        hcl = "x = <<EOF\nhello\nEOF\n"
        default = self._run_hcl_to_json(hcl)
        no_heredocs = self._run_hcl_to_json(hcl, ["--no-preserve-heredocs"])
        self.assertNotEqual(default, no_heredocs)

    def test_force_parens_flag(self):
        hcl = "x = 1 + 2 * 3\n"
        default = self._run_hcl_to_json(hcl)
        forced = self._run_hcl_to_json(hcl, ["--force-parens"])
        self.assertNotEqual(default, forced)
        self.assertIn("(", forced["x"])

    def test_no_preserve_scientific_flag(self):
        hcl = "x = 1e10\n"
        default = self._run_hcl_to_json(hcl)
        no_sci = self._run_hcl_to_json(hcl, ["--no-preserve-scientific"])
        self.assertNotEqual(default, no_sci)

    def test_json_indent_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, "x = {\n  a = 1\n}\n")

            stdout_2 = StringIO()
            stdout_4 = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--json-indent", "2", hcl_path]):
                with patch("sys.stdout", stdout_2):
                    main()
            with patch("sys.argv", ["hcl2tojson", "--json-indent", "4", hcl_path]):
                with patch("sys.stdout", stdout_4):
                    main()

            # 4-space indent produces longer output than 2-space
            self.assertGreater(len(stdout_4.getvalue()), len(stdout_2.getvalue()))

    def test_compact_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, "x = {\n  a = 1\n}\n")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--compact", hcl_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue().strip()
            # Compact = single line (no newlines inside the JSON)
            self.assertEqual(output.count("\n"), 0)
            data = json.loads(output)
            self.assertEqual(data["x"]["a"], 1)

    def test_tty_auto_indent(self):
        """When stdout is a TTY and no --json-indent, default to indent=2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, "x = {\n  a = 1\n}\n")

            stdout = StringIO()
            stdout.isatty = lambda: True  # type: ignore[assignment]
            with patch("sys.argv", ["hcl2tojson", hcl_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            # Indented = multiple lines
            self.assertGreater(output.count("\n"), 1)

    def test_non_tty_auto_compact(self):
        """When stdout is not a TTY and no --json-indent, default to compact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "test.tf")
            _write_file(hcl_path, "x = {\n  a = 1\n}\n")

            stdout = StringIO()
            # StringIO.isatty() returns False by default
            with patch("sys.argv", ["hcl2tojson", hcl_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue().strip()
            # Compact = single line
            self.assertEqual(output.count("\n"), 0)


class TestNdjsonStructuredErrors(TestCase):
    def test_ndjson_parse_error_is_json(self):
        """Fix #6: NDJSON mode emits structured JSON errors to stderr."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.tf")
            _write_file(path, "this is {{{{ not valid hcl")

            stderr = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--ndjson", path]):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)

            # stderr may contain progress line (filename) before the JSON error
            lines = [
                ln
                for ln in stderr.getvalue().strip().splitlines()
                if ln.startswith("{")
            ]
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data["error"], "parse_error")
            self.assertIn("message", data)
            self.assertIn("file", data)

    def test_non_ndjson_error_is_plain_text(self):
        """Non-NDJSON mode still uses plain text errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.tf")
            _write_file(path, "this is {{{{ not valid hcl")

            stderr = StringIO()
            with patch("sys.argv", ["hcl2tojson", path]):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)

            output = stderr.getvalue()
            self.assertIn("Error:", output)
            # Should NOT be JSON
            json_lines = [ln for ln in output.splitlines() if ln.startswith("{")]
            self.assertEqual(len(json_lines), 0)


class TestPartialFailureExitCode(TestCase):
    def test_directory_skip_exits_1(self):
        """Fix #3: directory mode with -s and partial failures should exit 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "good.tf"), SIMPLE_HCL)
            _write_file(os.path.join(in_dir, "bad.tf"), "this is {{{{ not valid")

            with patch("sys.argv", ["hcl2tojson", "-s", in_dir, "-o", out_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARTIAL)

            # Good file was still converted
            self.assertTrue(os.path.exists(os.path.join(out_dir, "good.json")))

    def test_multiple_files_skip_exits_1(self):
        """Fix #3: multi-file with -s and partial failures should exit 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            good = os.path.join(tmpdir, "good.tf")
            bad = os.path.join(tmpdir, "bad.tf")
            out_dir = os.path.join(tmpdir, "out")
            _write_file(good, SIMPLE_HCL)
            _write_file(bad, "this is {{{{ not valid")

            with patch("sys.argv", ["hcl2tojson", "-s", good, bad, "-o", out_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARTIAL)

    def test_all_success_exits_0(self):
        """No skips means exit 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "a.tf"), SIMPLE_HCL)
            _write_file(os.path.join(in_dir, "b.tf"), "y = 2\n")

            with patch("sys.argv", ["hcl2tojson", "-s", in_dir, "-o", out_dir]):
                main()  # should not raise SystemExit


class TestDirectoryEdgeCases(TestCase):
    def test_subdirectory_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            sub_dir = os.path.join(in_dir, "sub")
            out_dir = os.path.join(tmpdir, "output")
            os.makedirs(sub_dir)

            _write_file(os.path.join(sub_dir, "nested.tf"), SIMPLE_HCL)

            with patch("sys.argv", ["hcl2tojson", in_dir, "-o", out_dir]):
                main()

            self.assertTrue(os.path.exists(os.path.join(out_dir, "sub", "nested.json")))

    def test_directory_parse_error_exits_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "bad.tf"), "this is {{{{ not valid hcl")

            with patch("sys.argv", ["hcl2tojson", in_dir, "-o", out_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)


class TestStructuredErrors(TestCase):
    def test_io_error_structured_stderr(self):
        stderr = StringIO()
        with patch("sys.argv", ["hcl2tojson", "/nonexistent.tf"]):
            with patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_IO_ERROR)

        output = stderr.getvalue()
        self.assertIn("Error:", output)

    def test_parse_error_structured_stderr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.tf")
            _write_file(path, "this is {{{{ not valid hcl")

            stderr = StringIO()
            with patch("sys.argv", ["hcl2tojson", path]):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)

            output = stderr.getvalue()
            self.assertIn("Error:", output)


class TestQuietFlag(TestCase):
    def test_quiet_suppresses_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tf")
            _write_file(path, SIMPLE_HCL)

            stdout = StringIO()
            stderr = StringIO()
            with patch("sys.argv", ["hcl2tojson", "-q", path]):
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    main()

            # No progress output to stderr
            self.assertEqual(stderr.getvalue(), "")
            # But JSON still goes to stdout
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["x"], 1)

    def test_not_quiet_shows_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tf")
            _write_file(path, SIMPLE_HCL)

            stdout = StringIO()
            stderr = StringIO()
            with patch("sys.argv", ["hcl2tojson", path]):
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    main()

            self.assertIn("test.tf", stderr.getvalue())


class TestGlobExpansion(TestCase):
    def test_glob_pattern_expands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "a.tf"), "a = 1\n")
            _write_file(os.path.join(tmpdir, "b.tf"), "b = 2\n")

            stdout = StringIO()
            pattern = os.path.join(tmpdir, "*.tf")
            with patch("sys.argv", ["hcl2tojson", "--ndjson", pattern]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn('"a"', output)
            self.assertIn('"b"', output)


class TestNdjson(TestCase):
    def test_ndjson_flag_single_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tf")
            _write_file(path, SIMPLE_HCL)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--ndjson", path]):
                with patch("sys.stdout", stdout):
                    main()

            lines = stdout.getvalue().strip().split("\n")
            self.assertEqual(len(lines), 1)
            data = json.loads(lines[0])
            self.assertEqual(data["x"], 1)
            # Single file: no __file__ provenance
            self.assertNotIn("__file__", data)

    def test_ndjson_flag_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.tf")
            path_b = os.path.join(tmpdir, "b.tf")
            _write_file(path_a, "a = 1\n")
            _write_file(path_b, "b = 2\n")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--ndjson", path_a, path_b]):
                with patch("sys.stdout", stdout):
                    main()

            lines = stdout.getvalue().strip().split("\n")
            self.assertEqual(len(lines), 2)
            for line in lines:
                data = json.loads(line)
                self.assertIn("__file__", data)

    def test_ndjson_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            os.mkdir(in_dir)
            _write_file(os.path.join(in_dir, "a.tf"), "a = 1\n")
            _write_file(os.path.join(in_dir, "b.tf"), "b = 2\n")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--ndjson", in_dir]):
                with patch("sys.stdout", stdout):
                    main()

            lines = stdout.getvalue().strip().split("\n")
            self.assertEqual(len(lines), 2)
            files = set()
            for line in lines:
                data = json.loads(line)
                self.assertIn("__file__", data)
                files.add(data["__file__"])
            self.assertEqual(len(files), 2)

    def test_ndjson_skip_bad_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            os.mkdir(in_dir)
            _write_file(os.path.join(in_dir, "good.tf"), SIMPLE_HCL)
            _write_file(os.path.join(in_dir, "bad.tf"), "this is {{{{ not valid")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--ndjson", "-s", in_dir]):
                with patch("sys.stdout", stdout):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_PARTIAL)

            lines = [ln for ln in stdout.getvalue().strip().split("\n") if ln]
            self.assertEqual(len(lines), 1)


HCL_WITH_BLOCKS = """\
variable "name" {
  default = "hello"
}

resource "aws_instance" "main" {
  ami = "abc-123"
}

output "result" {
  value = "world"
}
"""


class TestBlockFiltering(TestCase):
    def test_only_single_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tf")
            _write_file(path, HCL_WITH_BLOCKS)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--only", "resource", path]):
                with patch("sys.stdout", stdout):
                    main()

            data = json.loads(stdout.getvalue())
            self.assertIn("resource", data)
            self.assertNotIn("variable", data)
            self.assertNotIn("output", data)

    def test_only_multiple_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tf")
            _write_file(path, HCL_WITH_BLOCKS)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--only", "resource,variable", path]):
                with patch("sys.stdout", stdout):
                    main()

            data = json.loads(stdout.getvalue())
            self.assertIn("resource", data)
            self.assertIn("variable", data)
            self.assertNotIn("output", data)

    def test_exclude_single_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tf")
            _write_file(path, HCL_WITH_BLOCKS)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--exclude", "variable", path]):
                with patch("sys.stdout", stdout):
                    main()

            data = json.loads(stdout.getvalue())
            self.assertNotIn("variable", data)
            self.assertIn("resource", data)
            self.assertIn("output", data)


class TestFieldProjection(TestCase):
    def test_fields_filter(self):
        hcl = "x = 1\ny = 2\nz = 3\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.tf")
            _write_file(path, hcl)

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "--fields", "x,y", path]):
                with patch("sys.stdout", stdout):
                    main()

            data = json.loads(stdout.getvalue())
            self.assertIn("x", data)
            self.assertIn("y", data)
            self.assertNotIn("z", data)
