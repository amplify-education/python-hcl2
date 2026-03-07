# pylint: disable=C0103,C0114,C0115,C0116
import os
import tempfile
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from cli.helpers import _convert_single_file, _convert_directory, _convert_stdin


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
