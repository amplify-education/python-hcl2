# pylint: disable=C0103,C0114,C0115,C0116
import json
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

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

            with patch("sys.argv", ["jsontohcl2", json_path, out_path]):
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

            with patch("sys.argv", ["jsontohcl2", in_dir, out_dir]):
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

            with patch("sys.argv", ["jsontohcl2", "-s", in_dir, out_dir]):
                main()

            self.assertTrue(os.path.exists(os.path.join(out_dir, "good.tf")))

    def test_invalid_path_raises_error(self):
        with patch("sys.argv", ["jsontohcl2", "/nonexistent/path/foo.json"]):
            with self.assertRaises(RuntimeError):
                main()
