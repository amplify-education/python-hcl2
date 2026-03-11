# pylint: disable=C0103,C0114,C0115,C0116
import json
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

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
                main()

            self.assertTrue(os.path.exists(os.path.join(out_dir, "good.json")))

    def test_directory_requires_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            os.mkdir(in_dir)
            _write_file(os.path.join(in_dir, "a.tf"), SIMPLE_HCL)

            with patch("sys.argv", ["hcl2tojson", in_dir]):
                with self.assertRaises(RuntimeError):
                    main()

    def test_multiple_files_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.tf")
            path_b = os.path.join(tmpdir, "b.tf")
            _write_file(path_a, "a = 1\n")
            _write_file(path_b, "b = 2\n")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", path_a, path_b]):
                with patch("sys.stdout", stdout):
                    main()

            output = stdout.getvalue()
            self.assertIn('"a"', output)
            self.assertIn('"b"', output)

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

    def test_multiple_files_invalid_path_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = os.path.join(tmpdir, "a.tf")
            _write_file(path_a, "a = 1\n")

            with patch("sys.argv", ["hcl2tojson", path_a, "/nonexistent.tf"]):
                with self.assertRaises(RuntimeError):
                    main()

    def test_invalid_path_raises_error(self):
        with patch("sys.argv", ["hcl2tojson", "/nonexistent/path/foo.tf"]):
            with self.assertRaises(RuntimeError):
                main()


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

    def test_raise_error_with_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.tf")
            out_path = os.path.join(tmpdir, "out.json")
            _write_file(in_path, "this is {{{{ not valid hcl")

            with patch("sys.argv", ["hcl2tojson", in_path, "-o", out_path]):
                with self.assertRaises(Exception):
                    main()

    def test_skip_error_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.tf")
            _write_file(in_path, "this is {{{{ not valid hcl")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", "-s", in_path]):
                with patch("sys.stdout", stdout):
                    main()

            self.assertEqual(stdout.getvalue(), "")

    def test_raise_error_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.tf")
            _write_file(in_path, "this is {{{{ not valid hcl")

            stdout = StringIO()
            with patch("sys.argv", ["hcl2tojson", in_path]):
                with patch("sys.stdout", stdout):
                    with self.assertRaises(Exception):
                        main()


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

    def test_directory_raise_error_without_skip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "bad.tf"), "this is {{{{ not valid hcl")

            with patch("sys.argv", ["hcl2tojson", in_dir, "-o", out_dir]):
                with self.assertRaises(Exception):
                    main()
