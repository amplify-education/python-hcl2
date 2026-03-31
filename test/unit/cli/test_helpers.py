# pylint: disable=C0103,C0114,C0115,C0116
import json
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from cli.helpers import (
    _collect_files,
    _convert_single_file,
    _convert_directory,
    _convert_multiple_files,
    _convert_stdin,
    _error,
    _expand_file_args,
)


def _write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestConvertSingleFile(TestCase):
    def test_does_not_close_stdout(self):
        """Regression test: stdout must not be closed after writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            _write_file(path, "hello")

            captured = StringIO()

            def convert(in_f, out_f):
                out_f.write(in_f.read())

            with patch("sys.stdout", captured):
                _convert_single_file(path, None, convert, False, (Exception,))

            self.assertFalse(captured.closed)
            self.assertIn("hello", captured.getvalue())

    def test_skip_error_with_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.txt")
            out_path = os.path.join(tmpdir, "out.txt")
            _write_file(in_path, "data")

            def convert(in_f, out_f):
                raise ValueError("boom")

            _convert_single_file(in_path, out_path, convert, True, (ValueError,))

    def test_raise_error_with_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.txt")
            out_path = os.path.join(tmpdir, "out.txt")
            _write_file(in_path, "data")

            def convert(in_f, out_f):
                raise ValueError("boom")

            with self.assertRaises(ValueError):
                _convert_single_file(in_path, out_path, convert, False, (ValueError,))

    def test_skip_error_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.txt")
            _write_file(in_path, "data")

            def convert(in_f, out_f):
                raise ValueError("boom")

            stdout = StringIO()
            with patch("sys.stdout", stdout):
                _convert_single_file(in_path, None, convert, True, (ValueError,))

            self.assertEqual(stdout.getvalue(), "")

    def test_raise_error_to_stdout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test.txt")
            _write_file(in_path, "data")

            def convert(in_f, out_f):
                raise ValueError("boom")

            stdout = StringIO()
            with patch("sys.stdout", stdout):
                with self.assertRaises(ValueError):
                    _convert_single_file(in_path, None, convert, False, (ValueError,))


class TestConvertDirectory(TestCase):
    def test_filters_by_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "a.tf"), "content")
            _write_file(os.path.join(in_dir, "b.txt"), "content")

            converted_files = []

            def convert(in_f, out_f):
                out_f.write(in_f.read())
                converted_files.append(True)

            _convert_directory(
                in_dir,
                out_dir,
                convert,
                False,
                (Exception,),
                in_extensions={".tf"},
                out_extension=".json",
            )

            self.assertEqual(len(converted_files), 1)
            self.assertTrue(os.path.exists(os.path.join(out_dir, "a.json")))
            self.assertFalse(os.path.exists(os.path.join(out_dir, "b.json")))

    def test_requires_out_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                _convert_directory(
                    tmpdir,
                    None,
                    lambda i, o: None,
                    False,
                    (Exception,),
                    in_extensions={".tf"},
                    out_extension=".json",
                )

    def test_subdirectory_creation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            sub_dir = os.path.join(in_dir, "sub")
            out_dir = os.path.join(tmpdir, "output")
            os.makedirs(sub_dir)

            _write_file(os.path.join(sub_dir, "nested.tf"), "content")

            def convert(in_f, out_f):
                out_f.write(in_f.read())

            _convert_directory(
                in_dir,
                out_dir,
                convert,
                False,
                (Exception,),
                in_extensions={".tf"},
                out_extension=".json",
            )

            self.assertTrue(os.path.exists(os.path.join(out_dir, "sub", "nested.json")))

    def test_raise_error_without_skip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_dir = os.path.join(tmpdir, "input")
            out_dir = os.path.join(tmpdir, "output")
            os.mkdir(in_dir)

            _write_file(os.path.join(in_dir, "bad.tf"), "data")

            def convert(in_f, out_f):
                raise ValueError("boom")

            with self.assertRaises(ValueError):
                _convert_directory(
                    in_dir,
                    out_dir,
                    convert,
                    False,
                    (ValueError,),
                    in_extensions={".tf"},
                    out_extension=".json",
                )


class TestConvertMultipleFiles(TestCase):
    def test_converts_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "a.tf"), "aaa")
            _write_file(os.path.join(tmpdir, "b.tf"), "bbb")

            out_dir = os.path.join(tmpdir, "out")
            converted = []

            def convert(in_f, out_f):
                converted.append(in_f.read())
                out_f.write("ok")

            _convert_multiple_files(
                [os.path.join(tmpdir, "a.tf"), os.path.join(tmpdir, "b.tf")],
                out_dir,
                convert,
                False,
                (Exception,),
                out_extension=".json",
            )

            self.assertEqual(len(converted), 2)
            self.assertTrue(os.path.exists(os.path.join(out_dir, "a.json")))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "b.json")))

    def test_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "a.tf"), "aaa")

            out_dir = os.path.join(tmpdir, "new_out")

            def convert(_in_f, out_f):
                out_f.write("ok")

            _convert_multiple_files(
                [os.path.join(tmpdir, "a.tf")],
                out_dir,
                convert,
                False,
                (Exception,),
                out_extension=".json",
            )

            self.assertTrue(os.path.isdir(out_dir))

    def test_skip_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "a.tf"), "aaa")
            _write_file(os.path.join(tmpdir, "b.tf"), "bbb")

            out_dir = os.path.join(tmpdir, "out")
            converted = []

            def convert(in_f, out_f):
                data = in_f.read()
                if "aaa" in data:
                    raise ValueError("boom")
                converted.append(data)
                out_f.write("ok")

            _convert_multiple_files(
                [os.path.join(tmpdir, "a.tf"), os.path.join(tmpdir, "b.tf")],
                out_dir,
                convert,
                True,
                (ValueError,),
                out_extension=".json",
            )

            self.assertEqual(len(converted), 1)

    def test_custom_out_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "a.json"), "data")

            out_dir = os.path.join(tmpdir, "out")

            def convert(_in_f, out_f):
                out_f.write("ok")

            _convert_multiple_files(
                [os.path.join(tmpdir, "a.json")],
                out_dir,
                convert,
                False,
                (Exception,),
                out_extension=".tf",
            )

            self.assertTrue(os.path.exists(os.path.join(out_dir, "a.tf")))


class TestConvertStdin(TestCase):
    def test_stdin_forward(self):
        stdout = StringIO()
        captured = []

        def convert(in_f, out_f):
            data = in_f.read()
            captured.append(data)
            out_f.write("output")

        with patch("sys.stdin", StringIO("input")), patch("sys.stdout", stdout):
            _convert_stdin(convert)

        self.assertEqual(captured[0], "input")
        self.assertIn("output", stdout.getvalue())


class TestError(TestCase):
    def test_plain_text(self):
        result = _error("something broke", use_json=False)
        self.assertEqual(result, "Error: something broke")

    def test_json_format(self):
        result = _error("parse failed", use_json=True, error_type="parse_error")
        data = json.loads(result)
        self.assertEqual(data["error"], "parse_error")
        self.assertEqual(data["message"], "parse failed")

    def test_json_extra_fields(self):
        result = _error("bad", use_json=True, error_type="io_error", file="x.tf")
        data = json.loads(result)
        self.assertEqual(data["file"], "x.tf")

    def test_json_default_error_type(self):
        result = _error("oops", use_json=True)
        data = json.loads(result)
        self.assertEqual(data["error"], "error")


class TestExpandFileArgs(TestCase):
    def test_literal_passthrough(self):
        self.assertEqual(_expand_file_args(["a.tf", "b.tf"]), ["a.tf", "b.tf"])

    def test_stdin_passthrough(self):
        self.assertEqual(_expand_file_args(["-"]), ["-"])

    def test_glob_expansion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "a.tf"), "")
            _write_file(os.path.join(tmpdir, "b.tf"), "")
            _write_file(os.path.join(tmpdir, "c.json"), "")

            result = _expand_file_args([os.path.join(tmpdir, "*.tf")])
            self.assertEqual(len(result), 2)
            self.assertTrue(all(r.endswith(".tf") for r in result))

    def test_no_match_keeps_literal(self):
        result = _expand_file_args(["/nonexistent/*.tf"])
        self.assertEqual(result, ["/nonexistent/*.tf"])


class TestCollectFiles(TestCase):
    def test_stdin(self):
        self.assertEqual(_collect_files("-", {".tf"}), ["-"])

    def test_single_file(self):
        with tempfile.NamedTemporaryFile(suffix=".tf", delete=False) as f:
            f.write(b"x = 1\n")
            path = f.name
        try:
            self.assertEqual(_collect_files(path, {".tf"}), [path])
        finally:
            os.unlink(path)

    def test_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "a.tf"), "")
            _write_file(os.path.join(tmpdir, "b.hcl"), "")
            _write_file(os.path.join(tmpdir, "c.txt"), "")

            result = _collect_files(tmpdir, {".tf", ".hcl"})
            basenames = [os.path.basename(f) for f in result]
            self.assertEqual(sorted(basenames), ["a.tf", "b.hcl"])

    def test_nonexistent_returns_literal(self):
        self.assertEqual(_collect_files("/no/such/path", {".tf"}), ["/no/such/path"])


class TestQuietMode(TestCase):
    def test_quiet_suppresses_stderr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            _write_file(path, "hello")

            stderr = StringIO()
            stdout = StringIO()

            def convert(in_f, out_f):
                out_f.write(in_f.read())

            with patch("sys.stderr", stderr), patch("sys.stdout", stdout):
                _convert_single_file(
                    path, None, convert, False, (Exception,), quiet=True
                )

            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("hello", stdout.getvalue())

    def test_not_quiet_prints_to_stderr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            _write_file(path, "hello")

            stderr = StringIO()
            stdout = StringIO()

            def convert(in_f, out_f):
                out_f.write(in_f.read())

            with patch("sys.stderr", stderr), patch("sys.stdout", stdout):
                _convert_single_file(
                    path, None, convert, False, (Exception,), quiet=False
                )

            self.assertIn("test.txt", stderr.getvalue())
