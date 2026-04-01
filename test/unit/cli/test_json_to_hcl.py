# pylint: disable=C0103,C0114,C0115,C0116
import json
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from cli.helpers import EXIT_DIFF, EXIT_IO_ERROR, EXIT_PARSE_ERROR, EXIT_PARTIAL
from cli.json_to_hcl import main


SIMPLE_JSON_DICT = {"x": 1}
SIMPLE_JSON = json.dumps(SIMPLE_JSON_DICT)

BLOCK_JSON_DICT = {"resource": [{"aws_instance": [{"example": [{"ami": "abc-123"}]}]}]}
BLOCK_JSON = json.dumps(BLOCK_JSON_DICT)


def _write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestJsonToHcl(TestCase):
    def test_single_file_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, SIMPLE_JSON)

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", json_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue().strip()
            self.assertIn("x", output)
            self.assertIn("1", output)

    def test_single_file_to_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            out_path = os.path.join(tmpdir, "test.tf")
            _write_file(json_path, SIMPLE_JSON)

            with patch("sys.argv", ["jsontohcl2", json_path, "-o", out_path]):
                main()

            output = _read_file(out_path)
            self.assertIn("x", output)
            self.assertIn("1", output)

    def test_stdin(self):
        stdout = StringIO()
        stdin = StringIO(SIMPLE_JSON)
        with patch("sys.argv", ["jsontohcl2", "-"]):
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                main()

        output = stdout.getvalue().strip()
        self.assertIn("x", output)
        self.assertIn("1", output)

    def test_directory_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "a.json"), SIMPLE_JSON)
            _write_file(os.path.join(in_dir, "readme.txt"), "not json")

            with patch("sys.argv", ["jsontohcl2", in_dir, "-o", out_dir]):
                main()

            self.assertTrue(os.path.exists(os.path.join(out_dir, "a.tf")))
            self.assertFalse(os.path.exists(os.path.join(out_dir, "readme.tf")))

    def test_indent_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, BLOCK_JSON)

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--indent", "4", json_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn("    ami", output)

    def test_no_align_flag(self):
        hcl_json = json.dumps({"short": 1, "very_long_name": 2})
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, hcl_json)

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--no-align", json_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            for line in output.strip().split("\n"):
                line = line.strip()
                if line.startswith("short"):
                    self.assertNotIn("  =", line)

    def test_colon_separator_flag(self):
        hcl_json = json.dumps({"x": {"a": 1}})
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, hcl_json)

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--colon-separator", json_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn(":", output)

    def test_skip_flag_on_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "good.json"), SIMPLE_JSON)
            _write_file(os.path.join(in_dir, "bad.json"), "{not valid json")

            with patch("sys.argv", ["jsontohcl2", "-s", in_dir, "-o", out_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARTIAL)

            self.assertTrue(os.path.exists(os.path.join(out_dir, "good.tf")))

    def test_skip_stdin_bad_input(self):
        """With -s, stdin JSON parse errors are skipped (no output, no crash)."""
        stdout = StringIO()
        stdin = StringIO("{not valid json")
        with patch("sys.argv", ["jsontohcl2", "-s", "-"]):
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                main()
        self.assertEqual(stdout.getvalue(), "")

    def test_multi_file_stdin_rejected(self):
        """Stdin (-) cannot be combined with other file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, SIMPLE_JSON)
            with self.assertRaises(SystemExit) as cm:
                with patch("sys.argv", ["jsontohcl2", json_path, "-", "-o", tmpdir]):
                    main()
            self.assertEqual(cm.exception.code, 2)  # argparse error

    def test_invalid_path_exits_4(self):
        with patch("sys.argv", ["jsontohcl2", "/nonexistent/path/foo.json"]):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, EXIT_IO_ERROR)

    def test_stdin_default_when_no_args(self):
        """No PATH args reads from stdin."""
        stdout = StringIO()
        stdin = StringIO(SIMPLE_JSON)
        with patch("sys.argv", ["jsontohcl2"]):
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                main()

        output = stdout.getvalue().strip()
        self.assertIn("x", output)
        self.assertIn("1", output)

    def test_multiple_files_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.json")
            path_b = os.path.join(tmpdir, "b.json")
            _write_file(path_a, json.dumps({"a": 1}))
            _write_file(path_b, json.dumps({"b": 2}))

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", path_a, path_b]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn("a", output)
            self.assertIn("b", output)

    def test_multiple_files_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.json")
            path_b = os.path.join(tmpdir, "b.json")
            out_dir = os.path.join(tmpdir, "out")
            _write_file(path_a, json.dumps({"a": 1}))
            _write_file(path_b, json.dumps({"b": 2}))

            with patch("sys.argv", ["jsontohcl2", path_a, path_b, "-o", out_dir]):
                main()

            self.assertTrue(os.path.exists(os.path.join(out_dir, "a.tf")))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "b.tf")))


class TestMutuallyExclusiveModes(TestCase):
    def test_diff_and_dry_run_rejected(self):
        """Fix #5: --diff and --dry-run cannot be combined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            _write_file(path, SIMPLE_JSON)

            stderr = StringIO()
            with patch(
                "sys.argv",
                ["jsontohcl2", "--diff", path, "--dry-run", path],
            ):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 2)

    def test_diff_and_fragment_rejected(self):
        """Fix #5: --diff and --fragment cannot be combined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            _write_file(path, SIMPLE_JSON)

            stderr = StringIO()
            with patch(
                "sys.argv",
                ["jsontohcl2", "--diff", path, "--fragment", path],
            ):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 2)

    def test_dry_run_and_fragment_rejected(self):
        """Fix #5: --dry-run and --fragment cannot be combined."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            _write_file(path, SIMPLE_JSON)

            stderr = StringIO()
            with patch(
                "sys.argv",
                ["jsontohcl2", "--dry-run", "--fragment", path],
            ):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, 2)


class TestDirectoryWithoutOutput(TestCase):
    def test_directory_without_output_errors(self):
        """Fix #1: jsontohcl2 dir/ without -o should error, not crash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            os.mkdir(in_dir)
            _write_file(os.path.join(in_dir, "a.json"), SIMPLE_JSON)

            with patch("sys.argv", ["jsontohcl2", in_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                # argparse parser.error() exits with code 2
                self.assertEqual(cm.exception.code, 2)


class TestPartialFailureExitCode(TestCase):
    def test_directory_skip_exits_1(self):
        """Fix #3: directory mode with -s and partial failures should exit 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "good.json"), SIMPLE_JSON)
            _write_file(os.path.join(in_dir, "bad.json"), "{not valid json")

            with patch("sys.argv", ["jsontohcl2", "-s", in_dir, "-o", out_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARTIAL)

    def test_multiple_files_skip_exits_1(self):
        """Fix #3: multi-file with -s and partial failures should exit 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            good = os.path.join(tmpdir, "good.json")
            bad = os.path.join(tmpdir, "bad.json")
            out_dir = os.path.join(tmpdir, "out")
            _write_file(good, SIMPLE_JSON)
            _write_file(bad, "{not valid json")

            with patch("sys.argv", ["jsontohcl2", "-s", good, bad, "-o", out_dir]):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARTIAL)

    def test_multiple_files_to_stdout_skip_exits_1(self):
        """Fix #3: multi-file to stdout with -s and partial failures should exit 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            good = os.path.join(tmpdir, "good.json")
            bad = os.path.join(tmpdir, "bad.json")
            _write_file(good, SIMPLE_JSON)
            _write_file(bad, "{not valid json")

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "-s", good, bad]):
                with patch("sys.stdout", stdout):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_PARTIAL)


class TestJsonToHclFlags(TestCase):
    def _run_json_to_hcl(self, json_dict, extra_flags=None):
        """Helper: write JSON to a temp file, run main() with flags, return HCL output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, json.dumps(json_dict))

            stdout = StringIO()
            argv = ["jsontohcl2"] + (extra_flags or []) + [json_path]
            with patch("sys.argv", argv):
                with patch("sys.stdout", stdout):
                    main()
            return stdout.getvalue()

    def test_no_trailing_comma_flag(self):
        data = {"x": {"a": 1, "b": 2}}
        default = self._run_json_to_hcl(data)
        no_comma = self._run_json_to_hcl(data, ["--no-trailing-comma"])
        # Default has trailing commas in objects; without flag it doesn't
        self.assertNotEqual(default, no_comma)

    def test_heredocs_to_strings_flag(self):
        # Serialized heredocs are quoted strings containing heredoc markers
        data = {"x": '"<<EOF\nhello\nEOF"'}
        default = self._run_json_to_hcl(data)
        converted = self._run_json_to_hcl(data, ["--heredocs-to-strings"])
        self.assertNotEqual(default, converted)
        # Default reconstructs as a real heredoc (no surrounding quotes);
        # with flag it stays as a quoted string
        self.assertNotIn('"', default.split("=", 1)[1].strip())
        self.assertIn('"', converted.split("=", 1)[1].strip())

    def test_strings_to_heredocs_flag(self):
        # Quoted strings with escaped newlines get converted to heredocs
        data = {"x": '"hello\\nworld"'}
        default = self._run_json_to_hcl(data)
        converted = self._run_json_to_hcl(data, ["--strings-to-heredocs"])
        self.assertNotEqual(default, converted)
        self.assertIn("<<", converted)

    def test_no_open_empty_blocks_flag(self):
        data = {"resource": [{'"a"': {'"b"': {"__is_block__": True}}}]}
        default = self._run_json_to_hcl(data)
        collapsed = self._run_json_to_hcl(data, ["--no-open-empty-blocks"])
        self.assertNotEqual(default, collapsed)
        # Default opens empty block on multiple lines; collapsed uses single line
        self.assertIn("{}", collapsed)

    def test_no_open_empty_objects_flag(self):
        data = {"x": {}}
        default = self._run_json_to_hcl(data)
        collapsed = self._run_json_to_hcl(data, ["--no-open-empty-objects"])
        self.assertNotEqual(default, collapsed)

    def test_open_empty_tuples_flag(self):
        data = {"x": []}
        default = self._run_json_to_hcl(data)
        expanded = self._run_json_to_hcl(data, ["--open-empty-tuples"])
        self.assertNotEqual(default, expanded)


class TestStructuredErrors(TestCase):
    def test_io_error_structured_stderr(self):
        stderr = StringIO()
        with patch("sys.argv", ["jsontohcl2", "/nonexistent.json"]):
            with patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_IO_ERROR)

        output = stderr.getvalue()
        self.assertIn("Error:", output)

    def test_invalid_json_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.json")
            _write_file(path, "{not valid json")

            stderr = StringIO()
            with patch("sys.argv", ["jsontohcl2", path]):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_PARTIAL)


class TestQuietFlag(TestCase):
    def test_quiet_suppresses_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            _write_file(path, SIMPLE_JSON)

            stdout = StringIO()
            stderr = StringIO()
            with patch("sys.argv", ["jsontohcl2", "-q", path]):
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    main()

            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("x", stdout.getvalue())

    def test_not_quiet_shows_progress(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            _write_file(path, SIMPLE_JSON)

            stdout = StringIO()
            stderr = StringIO()
            with patch("sys.argv", ["jsontohcl2", path]):
                with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                    main()

            self.assertIn("test.json", stderr.getvalue())


class TestDiffMode(TestCase):
    def test_diff_shows_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write original HCL
            original_path = os.path.join(tmpdir, "original.tf")
            _write_file(original_path, "x = 1\n")

            # Write modified JSON (x = 2)
            json_path = os.path.join(tmpdir, "modified.json")
            _write_file(json_path, json.dumps({"x": 2}))

            stdout = StringIO()
            with patch(
                "sys.argv",
                ["jsontohcl2", "--diff", original_path, json_path],
            ):
                with patch("sys.stdout", stdout):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    # Exit code 5 = differences found
                    self.assertEqual(cm.exception.code, EXIT_DIFF)

            diff_output = stdout.getvalue()
            self.assertIn("---", diff_output)
            self.assertIn("+++", diff_output)

    def test_diff_no_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "same.json")
            _write_file(json_path, json.dumps({"x": 1}))

            # Use --dry-run to get the exact HCL output
            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--dry-run", json_path]):
                with patch("sys.stdout", stdout):
                    main()

            original_path = os.path.join(tmpdir, "original.tf")
            _write_file(original_path, stdout.getvalue())

            # Now diff — should be identical (exit 0)
            stdout2 = StringIO()
            with patch(
                "sys.argv",
                ["jsontohcl2", "--diff", original_path, json_path],
            ):
                with patch("sys.stdout", stdout2):
                    main()

            self.assertEqual(stdout2.getvalue(), "")


class TestDryRun(TestCase):
    def test_dry_run_prints_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, SIMPLE_JSON)

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--dry-run", json_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn("x", output)
            self.assertIn("1", output)


class TestFragment(TestCase):
    def test_fragment_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "frag.json")
            _write_file(json_path, json.dumps({"bucket": "my-data", "acl": "private"}))

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--fragment", json_path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn("bucket", output)
            self.assertIn("acl", output)
            self.assertIn("my-data", output)

    def test_fragment_from_stdin(self):
        stdin = StringIO(json.dumps({"cpu": 512}))
        stdout = StringIO()
        with patch("sys.argv", ["jsontohcl2", "--fragment", "-"]):
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                main()

        output = stdout.getvalue()
        self.assertIn("cpu", output)
        self.assertIn("512", output)

    def test_fragment_strips_block_markers(self):
        """The distinguishing feature of --fragment: __is_block__ markers are removed."""
        data = {
            "resource": [
                {
                    "aws_instance": {
                        "main": {"ami": "abc-123", "__is_block__": True},
                        "__is_block__": True,
                    }
                }
            ],
            "__is_block__": True,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "frag.json")
            _write_file(path, json.dumps(data))

            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--fragment", path]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            # Should produce attribute-style output (no block syntax)
            self.assertIn("resource", output)
            self.assertNotIn("__is_block__", output)

    def test_fragment_rejects_non_dict(self):
        """--fragment with a JSON array should exit 2 (structure error)."""
        stdin = StringIO("[1, 2, 3]")
        stderr = StringIO()
        with patch("sys.argv", ["jsontohcl2", "--fragment", "-"]):
            with patch("sys.stdin", stdin), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)


class TestStructureError(TestCase):
    def test_structure_error_exits_2(self):
        """TypeError/KeyError/ValueError from dump() should exit 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "valid.json")
            _write_file(path, SIMPLE_JSON)

            stderr = StringIO()
            with patch("sys.argv", ["jsontohcl2", path]):
                with patch(
                    "cli.json_to_hcl.dump", side_effect=TypeError("bad structure")
                ):
                    with patch("sys.stderr", stderr):
                        with self.assertRaises(SystemExit) as cm:
                            main()
                        self.assertEqual(cm.exception.code, EXIT_PARSE_ERROR)

            output = stderr.getvalue()
            self.assertIn("Error:", output)
            self.assertIn("bad structure", output)


class TestDiffEdgeCases(TestCase):
    def test_diff_nonexistent_original_exits_4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, SIMPLE_JSON)

            stderr = StringIO()
            with patch(
                "sys.argv",
                ["jsontohcl2", "--diff", "/nonexistent.tf", json_path],
            ):
                with patch("sys.stderr", stderr):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_IO_ERROR)

    def test_diff_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = os.path.join(tmpdir, "original.tf")
            _write_file(original_path, "x = 1\n")

            stdin = StringIO(json.dumps({"x": 2}))
            stdout = StringIO()
            with patch("sys.argv", ["jsontohcl2", "--diff", original_path, "-"]):
                with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    self.assertEqual(cm.exception.code, EXIT_DIFF)

            self.assertIn("---", stdout.getvalue())
