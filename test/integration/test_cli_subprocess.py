"""Subprocess-based integration tests for hcl2tojson and jsontohcl2 CLIs.

These tests invoke the CLIs as real external processes via subprocess.run(),
verifying behavior that cannot be tested with mocked sys.argv/stdout/stdin:
real exit codes, stdout/stderr separation, stdin piping, pipe composition
between the two CLIs, and TTY vs pipe default behavior.

Golden fixtures are reused from test/integration/hcl2_original/, json_serialized/,
hcl2_reconstructed/, and json_reserialized/.
"""
# pylint: disable=C0103,C0114,C0115,C0116

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional
from unittest import TestCase

INTEGRATION_DIR = Path(__file__).absolute().parent
HCL_DIR = INTEGRATION_DIR / "hcl2_original"
JSON_DIR = INTEGRATION_DIR / "json_serialized"
HCL_RECONSTRUCTED_DIR = INTEGRATION_DIR / "hcl2_reconstructed"
JSON_RESERIALIZED_DIR = INTEGRATION_DIR / "json_reserialized"
PROJECT_ROOT = INTEGRATION_DIR.parent.parent

_HCL2TOJSON = [sys.executable, "-c", "from cli.hcl_to_json import main; main()"]
_JSONTOHCL2 = [sys.executable, "-c", "from cli.json_to_hcl import main; main()"]

_TIMEOUT = 30


def _get_suites() -> List[str]:
    return sorted(f.stem for f in HCL_DIR.iterdir() if f.is_file())


def _run_hcl2tojson(
    *args: str,
    stdin: Optional[str] = None,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        _HCL2TOJSON + list(args),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        cwd=cwd or str(PROJECT_ROOT),
        check=False,
    )


def _run_jsontohcl2(
    *args: str,
    stdin: Optional[str] = None,
    cwd: Optional[str] = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        _JSONTOHCL2 + list(args),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
        cwd=cwd or str(PROJECT_ROOT),
        check=False,
    )


def _write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestHcl2ToJsonExitCodes(TestCase):
    def test_success_exits_0(self):
        result = _run_hcl2tojson(str(HCL_DIR / "nulls.tf"))
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

    def test_file_not_found_exits_4(self):
        result = _run_hcl2tojson("/nonexistent/path.tf")
        self.assertEqual(result.returncode, 4)

    def test_parse_error_exits_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = os.path.join(tmpdir, "bad.tf")
            _write_file(bad, "{{{")
            result = _run_hcl2tojson(bad)
            self.assertEqual(result.returncode, 2)

    def test_skip_partial_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            indir = os.path.join(tmpdir, "in")
            outdir = os.path.join(tmpdir, "out")
            os.mkdir(indir)
            _write_file(os.path.join(indir, "good.tf"), "x = 1\n")
            _write_file(os.path.join(indir, "bad.tf"), "{{{")
            result = _run_hcl2tojson("-s", indir, "-o", outdir)
            self.assertEqual(result.returncode, 1, f"stderr: {result.stderr}")

    def test_ndjson_all_fail_with_skip_exits_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_file(os.path.join(tmpdir, "bad1.tf"), "{{{")
            _write_file(os.path.join(tmpdir, "bad2.tf"), "<<<")
            result = _run_hcl2tojson("--ndjson", "-s", tmpdir)
            self.assertEqual(result.returncode, 2, f"stderr: {result.stderr}")

    def test_directory_without_ndjson_or_output_errors(self):
        result = _run_hcl2tojson(str(HCL_DIR))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--ndjson", result.stderr)

    def test_stdin_skip_bad_input_exits_1(self):
        result = _run_hcl2tojson("-s", "-", stdin="{{{")
        # Skip mode: bad stdin is skipped gracefully (not exit 2), partial exit
        self.assertEqual(result.returncode, 1, f"stderr: {result.stderr}")

    def test_single_file_skip_to_output_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = os.path.join(tmpdir, "bad.tf")
            out = os.path.join(tmpdir, "out.json")
            _write_file(bad, "{{{")
            result = _run_hcl2tojson("-s", bad, "-o", out)
            self.assertEqual(result.returncode, 1, f"stderr: {result.stderr}")
            self.assertFalse(os.path.exists(out))


class TestJsonToHclExitCodes(TestCase):
    def test_success_exits_0(self):
        result = _run_jsontohcl2(str(JSON_DIR / "nulls.json"))
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

    def test_file_not_found_exits_4(self):
        result = _run_jsontohcl2("/nonexistent/path.json")
        self.assertEqual(result.returncode, 4)

    def test_invalid_json_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = os.path.join(tmpdir, "bad.json")
            _write_file(bad, "{bad json")
            result = _run_jsontohcl2(bad)
            self.assertEqual(result.returncode, 1)

    def test_structure_error_exits_2(self):
        result = _run_jsontohcl2("--fragment", "-", stdin="[1,2,3]")
        self.assertEqual(result.returncode, 2)

    def test_diff_with_differences_exits_5(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            modified = os.path.join(tmpdir, "modified.json")
            _write_file(modified, json.dumps({"x": 999}))
            original_tf = str(HCL_RECONSTRUCTED_DIR / "nulls.tf")
            result = _run_jsontohcl2("--diff", original_tf, modified)
            self.assertEqual(result.returncode, 5, f"stderr: {result.stderr}")

    def test_diff_identical_exits_0(self):
        result = _run_jsontohcl2(
            "--diff",
            str(HCL_RECONSTRUCTED_DIR / "nulls.tf"),
            str(JSON_DIR / "nulls.json"),
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

    def test_directory_without_output_errors(self):
        result = _run_jsontohcl2(str(JSON_DIR))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("-o", result.stderr)


# ---------------------------------------------------------------------------
# Stdout / stderr separation
# ---------------------------------------------------------------------------


class TestStdoutStderrSeparation(TestCase):
    def test_hcl2tojson_json_on_stdout_progress_on_stderr(self):
        fixture = str(HCL_DIR / "nulls.tf")
        result = _run_hcl2tojson(fixture)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        json.loads(result.stdout)  # stdout must be valid JSON
        self.assertIn("nulls.tf", result.stderr)

    def test_hcl2tojson_quiet_suppresses_stderr(self):
        result = _run_hcl2tojson("-q", str(HCL_DIR / "nulls.tf"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        json.loads(result.stdout)

    def test_hcl2tojson_error_on_stderr_only(self):
        result = _run_hcl2tojson("/nonexistent/path.tf")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Error:", result.stderr)

    def test_jsontohcl2_hcl_on_stdout_progress_on_stderr(self):
        fixture = str(JSON_DIR / "nulls.json")
        result = _run_jsontohcl2(fixture)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("terraform", result.stdout)
        self.assertIn("nulls.json", result.stderr)

    def test_jsontohcl2_quiet_suppresses_stderr(self):
        result = _run_jsontohcl2("-q", str(JSON_DIR / "nulls.json"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("terraform", result.stdout)


# ---------------------------------------------------------------------------
# Stdin piping
# ---------------------------------------------------------------------------


class TestStdinPiping(TestCase):
    def test_hcl2tojson_reads_stdin(self):
        result = _run_hcl2tojson(stdin="x = 1\n")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["x"], 1)

    def test_jsontohcl2_reads_stdin(self):
        result = _run_jsontohcl2(stdin='{"x": 1}')
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("x", result.stdout)
        self.assertIn("1", result.stdout)

    def test_hcl2tojson_stdin_explicit_dash(self):
        result = _run_hcl2tojson("-", stdin="x = 1\n")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertEqual(data["x"], 1)

    def test_jsontohcl2_stdin_explicit_dash(self):
        result = _run_jsontohcl2("-", stdin='{"x": 1}')
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("x", result.stdout)
        self.assertIn("1", result.stdout)

    def test_hcl2tojson_stdin_to_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "out.json")
            result = _run_hcl2tojson("-", "-o", out, stdin="x = 1\n")
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["x"], 1)

    def test_jsontohcl2_stdin_to_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "out.tf")
            result = _run_jsontohcl2("-", "-o", out, stdin='{"x": 1}')
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            with open(out, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("x", content)
            self.assertIn("1", content)


# ---------------------------------------------------------------------------
# Pipe composition (highest value)
# ---------------------------------------------------------------------------


class TestPipeComposition(TestCase):
    maxDiff = None

    def test_hcl_to_json_to_hcl_round_trip(self):
        """hcl2tojson <file> | jsontohcl2 | hcl2tojson — JSON must match."""
        for suite in _get_suites():
            with self.subTest(suite=suite):
                hcl_path = str(HCL_DIR / f"{suite}.tf")

                step1 = _run_hcl2tojson(hcl_path)
                self.assertEqual(step1.returncode, 0, f"step1 stderr: {step1.stderr}")

                step2 = _run_jsontohcl2(stdin=step1.stdout)
                self.assertEqual(step2.returncode, 0, f"step2 stderr: {step2.stderr}")

                step3 = _run_hcl2tojson(stdin=step2.stdout)
                self.assertEqual(step3.returncode, 0, f"step3 stderr: {step3.stderr}")

                json1 = json.loads(step1.stdout)
                json3 = json.loads(step3.stdout)
                self.assertEqual(
                    json3,
                    json1,
                    f"HCL -> JSON -> HCL -> JSON mismatch for {suite}",
                )

    def test_json_to_hcl_to_json_round_trip(self):
        """jsontohcl2 <file> | hcl2tojson — JSON must match reserialized golden."""
        for suite in _get_suites():
            with self.subTest(suite=suite):
                json_path = str(JSON_DIR / f"{suite}.json")
                golden_path = JSON_RESERIALIZED_DIR / f"{suite}.json"

                step1 = _run_jsontohcl2(json_path)
                self.assertEqual(step1.returncode, 0, f"step1 stderr: {step1.stderr}")

                step2 = _run_hcl2tojson(stdin=step1.stdout)
                self.assertEqual(step2.returncode, 0, f"step2 stderr: {step2.stderr}")

                actual = json.loads(step2.stdout)
                expected = json.loads(golden_path.read_text())
                self.assertEqual(
                    actual,
                    expected,
                    f"JSON -> HCL -> JSON mismatch for {suite}",
                )

    def test_round_trip_matches_golden_hcl(self):
        """hcl2tojson <file> | jsontohcl2 — HCL must match reconstructed golden."""
        for suite in _get_suites():
            with self.subTest(suite=suite):
                hcl_path = str(HCL_DIR / f"{suite}.tf")
                golden_path = HCL_RECONSTRUCTED_DIR / f"{suite}.tf"

                step1 = _run_hcl2tojson(hcl_path)
                self.assertEqual(step1.returncode, 0, f"step1 stderr: {step1.stderr}")

                step2 = _run_jsontohcl2(stdin=step1.stdout)
                self.assertEqual(step2.returncode, 0, f"step2 stderr: {step2.stderr}")

                # The CLI helper appends a trailing newline after conversion
                # output, so normalize before comparing with golden files.
                expected = golden_path.read_text()
                actual = step2.stdout.rstrip("\n") + "\n"
                self.assertMultiLineEqual(actual, expected)


# ---------------------------------------------------------------------------
# File output (-o flag)
# ---------------------------------------------------------------------------


class TestFileOutput(TestCase):
    maxDiff = None

    def test_hcl2tojson_single_file_to_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "out.json")
            fixture = str(HCL_DIR / "nulls.tf")
            golden = JSON_DIR / "nulls.json"

            result = _run_hcl2tojson(fixture, "-o", out_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

            with open(out_path, encoding="utf-8") as f:
                actual = json.load(f)
            expected = json.loads(golden.read_text())
            self.assertEqual(actual, expected)

    def test_jsontohcl2_single_file_to_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "out.tf")
            fixture = str(JSON_DIR / "nulls.json")

            result = _run_jsontohcl2(fixture, "-o", out_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

            with open(out_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("terraform", content)

    def test_hcl2tojson_directory_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "out")
            result = _run_hcl2tojson(str(HCL_DIR), "-o", outdir)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

            expected_files = {f"{s}.json" for s in _get_suites()}
            actual_files = set(os.listdir(outdir))
            self.assertEqual(actual_files, expected_files)

    def test_jsontohcl2_directory_to_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "out")
            result = _run_jsontohcl2(str(JSON_DIR), "-o", outdir)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

            expected_files = {f"{s}.tf" for s in _get_suites()}
            actual_files = set(os.listdir(outdir))
            self.assertEqual(actual_files, expected_files)


# ---------------------------------------------------------------------------
# NDJSON mode
# ---------------------------------------------------------------------------


class TestNdjsonSubprocess(TestCase):
    def test_ndjson_single_file(self):
        result = _run_hcl2tojson("--ndjson", str(HCL_DIR / "nulls.tf"))
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        lines = result.stdout.strip().split("\n")
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertNotIn("__file__", data)

    def test_ndjson_directory(self):
        result = _run_hcl2tojson("--ndjson", str(HCL_DIR))
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        lines = result.stdout.strip().split("\n")
        self.assertEqual(len(lines), len(_get_suites()))
        for line in lines:
            data = json.loads(line)
            self.assertIn("__file__", data)

    def test_ndjson_from_stdin(self):
        result = _run_hcl2tojson("--ndjson", "-", stdin="x = 1\n")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        lines = result.stdout.strip().split("\n")
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data["x"], 1)

    def test_ndjson_parse_error_structured_json_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = os.path.join(tmpdir, "bad.tf")
            _write_file(bad, "{{{")
            result = _run_hcl2tojson("--ndjson", bad)
            self.assertEqual(result.returncode, 2)
            # NDJSON mode emits structured JSON errors to stderr
            # (stderr may also contain the filename progress line)
            json_lines = []
            for line in result.stderr.strip().splitlines():
                try:
                    json_lines.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            self.assertTrue(json_lines, f"No JSON error on stderr: {result.stderr}")
            err = json_lines[0]
            self.assertIn("error", err)
            self.assertIn("message", err)

    def test_ndjson_all_io_fail_with_skip_exits_4(self):
        result = _run_hcl2tojson(
            "--ndjson", "-s", "/nonexistent/a.tf", "/nonexistent/b.tf"
        )
        # All-fail with IO errors should exit 4 (EXIT_IO_ERROR), not 2
        self.assertEqual(result.returncode, 4, f"stderr: {result.stderr}")

    def test_ndjson_only_filter_skips_empty(self):
        result = _run_hcl2tojson(
            "--ndjson", "--only", "nonexistent_block_type", str(HCL_DIR / "nulls.tf")
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # No NDJSON line emitted when all data is filtered out
        self.assertEqual(result.stdout.strip(), "")

    def test_ndjson_json_indent_warning(self):
        result = _run_hcl2tojson(
            "--ndjson", "--json-indent", "2", str(HCL_DIR / "nulls.tf")
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ignored", result.stderr.lower())


# ---------------------------------------------------------------------------
# Compact / indent output
# ---------------------------------------------------------------------------


class TestCompactOutput(TestCase):
    def test_compact_flag_single_line(self):
        result = _run_hcl2tojson("--compact", str(HCL_DIR / "nulls.tf"))
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # Compact output: only a trailing newline, no interior newlines
        content = result.stdout.rstrip("\n")
        self.assertNotIn("\n", content)
        # Truly compact: no spaces after separators (uses ",:" not ", : ")
        self.assertNotRegex(content, r'": ')
        self.assertNotRegex(content, r", ")

    def test_pipe_default_is_compact(self):
        # When stdout is a pipe (not TTY), the default is compact output.
        # This code path cannot be tested in unit tests that mock sys.stdout.
        result = _run_hcl2tojson(str(HCL_DIR / "nulls.tf"))
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        content = result.stdout.rstrip("\n")
        self.assertNotIn("\n", content)

    def test_json_indent_overrides_default(self):
        result = _run_hcl2tojson("--json-indent", "2", str(HCL_DIR / "nulls.tf"))
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # Indented output should have multiple lines
        lines = result.stdout.strip().split("\n")
        self.assertGreater(len(lines), 1)


# ---------------------------------------------------------------------------
# Diff mode
# ---------------------------------------------------------------------------


class TestDiffMode(TestCase):
    def test_diff_shows_differences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            modified = os.path.join(tmpdir, "modified.json")
            _write_file(modified, json.dumps({"x": 999}))
            original = str(HCL_RECONSTRUCTED_DIR / "nulls.tf")

            result = _run_jsontohcl2("--diff", original, modified)
            self.assertEqual(result.returncode, 5, f"stderr: {result.stderr}")
            self.assertIn("---", result.stdout)
            self.assertIn("+++", result.stdout)

    def test_diff_no_differences(self):
        result = _run_jsontohcl2(
            "--diff",
            str(HCL_RECONSTRUCTED_DIR / "nulls.tf"),
            str(JSON_DIR / "nulls.json"),
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertEqual(result.stdout, "")

    def test_diff_from_stdin(self):
        json_text = (JSON_DIR / "nulls.json").read_text()
        result = _run_jsontohcl2(
            "--diff", str(HCL_RECONSTRUCTED_DIR / "nulls.tf"), "-", stdin=json_text
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertEqual(result.stdout, "")


# ---------------------------------------------------------------------------
# Fragment mode
# ---------------------------------------------------------------------------


class TestSemanticDiffMode(TestCase):
    def test_semantic_diff_no_changes_exits_0(self):
        """Round-trip HCL→JSON should show no semantic differences."""
        for suite in _get_suites():
            with self.subTest(suite=suite):
                hcl_path = str(HCL_DIR / f"{suite}.tf")
                json_path = str(JSON_DIR / f"{suite}.json")
                result = _run_jsontohcl2("--semantic-diff", hcl_path, json_path)
                self.assertEqual(
                    result.returncode,
                    0,
                    f"Unexpected diff for {suite}:\n{result.stdout}",
                )
                self.assertEqual(result.stdout, "")

    def test_semantic_diff_detects_value_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "original.tf")
            json_path = os.path.join(tmpdir, "modified.json")
            _write_file(hcl_path, "x = 1\n")
            _write_file(json_path, json.dumps({"x": 2}))

            result = _run_jsontohcl2("--semantic-diff", hcl_path, json_path)
            self.assertEqual(result.returncode, 5)
            self.assertIn("x", result.stdout)
            self.assertIn("~", result.stdout)

    def test_semantic_diff_ignores_formatting(self):
        """Text diff would show changes; semantic diff should show none."""
        hcl = 'resource "aws_instance" "main" {\n  ami = "abc-123"\n}\n'
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "original.tf")
            json_path = os.path.join(tmpdir, "modified.json")
            _write_file(hcl_path, hcl)

            # Convert to JSON first, then semantic-diff against original
            step1 = _run_hcl2tojson(hcl_path)
            self.assertEqual(step1.returncode, 0, f"step1 stderr: {step1.stderr}")
            _write_file(json_path, step1.stdout)

            # Text diff would show formatting noise; semantic diff should be clean
            result = _run_jsontohcl2("--semantic-diff", hcl_path, json_path)
            self.assertEqual(result.returncode, 0, f"stdout: {result.stdout}")
            self.assertEqual(result.stdout, "")

    def test_semantic_diff_json_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "original.tf")
            json_path = os.path.join(tmpdir, "modified.json")
            _write_file(hcl_path, "x = 1\n")
            _write_file(json_path, json.dumps({"x": 2}))

            result = _run_jsontohcl2(
                "--semantic-diff", hcl_path, "--diff-json", json_path
            )
            self.assertEqual(result.returncode, 5)
            entries = json.loads(result.stdout)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["kind"], "changed")
            self.assertEqual(entries[0]["path"], "x")

    def test_semantic_diff_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hcl_path = os.path.join(tmpdir, "original.tf")
            _write_file(hcl_path, "x = 1\n")

            result = _run_jsontohcl2(
                "--semantic-diff", hcl_path, "-", stdin=json.dumps({"x": 99})
            )
            self.assertEqual(result.returncode, 5)
            self.assertIn("x", result.stdout)

    def test_semantic_diff_file_not_found_exits_4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "test.json")
            _write_file(json_path, '{"x": 1}')

            result = _run_jsontohcl2("--semantic-diff", "/nonexistent.tf", json_path)
            self.assertEqual(result.returncode, 4)
            self.assertIn("Error:", result.stderr)

    def test_semantic_diff_pipe_composition(self):
        """hcl2tojson | modify | jsontohcl2 --semantic-diff — should detect changes."""
        hcl_path = str(HCL_DIR / "nulls.tf")
        step1 = _run_hcl2tojson(hcl_path)
        self.assertEqual(step1.returncode, 0, f"step1 stderr: {step1.stderr}")

        # Modify one value in the JSON
        data = json.loads(step1.stdout)
        data["x_injected_key"] = 42
        modified_json = json.dumps(data)

        result = _run_jsontohcl2("--semantic-diff", hcl_path, "-", stdin=modified_json)
        self.assertEqual(result.returncode, 5)
        self.assertIn("x_injected_key", result.stdout)


class TestFragmentMode(TestCase):
    def test_fragment_from_stdin(self):
        result = _run_jsontohcl2(
            "--fragment", "-", stdin='{"cpu": 512, "memory": 1024}'
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("cpu", result.stdout)
        self.assertIn("512", result.stdout)
        self.assertIn("memory", result.stdout)
        self.assertIn("1024", result.stdout)

    def test_fragment_strips_is_block_markers(self):
        """hcl2tojson output piped to jsontohcl2 --fragment strips __is_block__."""
        step1 = _run_hcl2tojson(str(HCL_DIR / "nulls.tf"))
        self.assertEqual(step1.returncode, 0, f"step1 stderr: {step1.stderr}")
        result = _run_jsontohcl2("--fragment", "-", stdin=step1.stdout)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertNotIn("__is_block__", result.stdout)
        self.assertIn("terraform", result.stdout)


# ---------------------------------------------------------------------------
# Stdout buffering with skip
# ---------------------------------------------------------------------------


class TestFieldsProjection(TestCase):
    def test_fields_does_not_leak_leaf_lists(self):
        """--fields should drop leaf list values not in the field set."""
        hcl = (
            'module "test" {\n'
            '  source  = "../../modules/test/v1"\n'
            "  cpu     = 1024\n"
            "  memory  = 2048\n"
            '  regions = ["us-east-1", "us-west-2"]\n'
            '  tags    = { env = "prod" }\n'
            "}\n"
        )
        result = _run_hcl2tojson(
            "--only", "module", "--fields", "cpu,memory", stdin=hcl
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        block = data["module"][0]['"test"']
        self.assertIn("cpu", block)
        self.assertIn("memory", block)
        self.assertNotIn("regions", block)
        self.assertNotIn("tags", block)
        self.assertNotIn("source", block)

    def test_fields_preserves_structural_lists(self):
        """--fields should still recurse into block-wrapping lists."""
        hcl = (
            'resource "aws_instance" "main" {\n'
            '  ami           = "abc-123"\n'
            '  instance_type = "t2.micro"\n'
            '  tags          = { env = "prod" }\n'
            "}\n"
        )
        result = _run_hcl2tojson("--fields", "ami", stdin=hcl)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        data = json.loads(result.stdout)
        block = data["resource"][0]['"aws_instance"']['"main"']
        self.assertIn("ami", block)
        self.assertNotIn("instance_type", block)
        self.assertNotIn("tags", block)


class TestNonDictJsonRejection(TestCase):
    def test_dry_run_list_json_exits_2(self):
        result = _run_jsontohcl2("--dry-run", "-", stdin='["a", "b"]')
        self.assertEqual(result.returncode, 2)
        self.assertIn("Error:", result.stderr)

    def test_dry_run_scalar_json_exits_2(self):
        result = _run_jsontohcl2("--dry-run", "-", stdin="42")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Error:", result.stderr)

    def test_normal_mode_list_json_exits_2(self):
        result = _run_jsontohcl2(stdin='["a", "b"]')
        self.assertEqual(result.returncode, 2)
        self.assertIn("Error:", result.stderr)

    def test_fragment_still_rejects_non_dict(self):
        result = _run_jsontohcl2("--fragment", "-", stdin="[1, 2, 3]")
        self.assertEqual(result.returncode, 2)


class TestStdoutBuffering(TestCase):
    def test_skip_no_partial_stdout_on_failure(self):
        """With -s, a failed file should not leave partial output on stdout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            outdir = os.path.join(tmpdir, "out")
            indir = os.path.join(tmpdir, "in")
            os.mkdir(indir)
            _write_file(os.path.join(indir, "good.tf"), "x = 1\n")
            _write_file(os.path.join(indir, "bad.tf"), "{{{")

            result = _run_hcl2tojson("-s", indir, "-o", outdir)
            self.assertEqual(result.returncode, 1)
            # good.tf should produce output, bad.tf should not
            self.assertTrue(os.path.exists(os.path.join(outdir, "good.json")))
            self.assertFalse(os.path.exists(os.path.join(outdir, "bad.json")))


# ---------------------------------------------------------------------------
# Multi-file basename collision
# ---------------------------------------------------------------------------


class TestMultiFileCollision(TestCase):
    def test_basename_collision_preserves_directory_structure(self):
        """Files with same basename from different dirs get separate output paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = os.path.join(tmpdir, "dir1")
            dir2 = os.path.join(tmpdir, "dir2")
            outdir = os.path.join(tmpdir, "out")
            os.mkdir(dir1)
            os.mkdir(dir2)
            _write_file(os.path.join(dir1, "main.tf"), "x = 1\n")
            _write_file(os.path.join(dir2, "main.tf"), "y = 2\n")

            result = _run_hcl2tojson(
                os.path.join(dir1, "main.tf"),
                os.path.join(dir2, "main.tf"),
                "-o",
                outdir,
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")

            # Both files should exist in output, not overwrite each other
            out_files = []
            for root, _dirs, files in os.walk(outdir):
                for fname in files:
                    out_files.append(os.path.join(root, fname))
            self.assertEqual(
                len(out_files), 2, f"Expected 2 output files, got: {out_files}"
            )

            # Each should contain different data
            contents = set()
            for path in out_files:
                with open(path, encoding="utf-8") as fobj:
                    contents.add(fobj.read())
            self.assertEqual(
                len(contents), 2, "Output files should have different content"
            )
