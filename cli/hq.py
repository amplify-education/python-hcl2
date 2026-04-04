"""``hq`` CLI entry point — query HCL2 files."""

import argparse
import dataclasses
import json
import multiprocessing
import os
import sys
from typing import Any, List, Optional, Tuple

from hcl2.query._base import NodeView
from hcl2.utils import SerializationOptions
from hcl2.query.body import DocumentView
from hcl2.query.introspect import build_schema, describe_results
from hcl2.query.path import QuerySyntaxError
from hcl2.query.pipeline import classify_stage, execute_pipeline, split_pipeline
from hcl2.query.resolver import resolve_path
from hcl2.query.safe_eval import (
    UnsafeExpressionError,
    _SAFE_CALLABLE_NAMES,
    safe_eval,
)
from hcl2.version import __version__
from .helpers import _expand_file_args  # noqa: F401 — re-exported for tests

# Exit codes
EXIT_SUCCESS = 0
EXIT_NO_RESULTS = 1
EXIT_PARSE_ERROR = 2
EXIT_QUERY_ERROR = 3
EXIT_IO_ERROR = 4

EXAMPLES_TEXT = """\
examples:
  # Structural queries
  hq 'resource.aws_instance.main.ami' main.tf
  hq 'variable[*]' variables.tf --json
  echo 'x = 1' | hq 'x' --value

  # Multiple files and globs
  hq 'resource[*]' file1.tf file2.tf --json
  hq 'variable[*]' modules/ --ndjson
  hq 'resource[*]' 'modules/**/*.tf' --json

  # Pipes
  hq 'resource.aws_instance[*] | .tags' main.tf
  hq 'variable[*] | select(.default) | .default' vars.tf --json

  # Builtins
  hq 'x | keys' file.tf --json
  hq 'x | length' file.tf --value

  # Select (bracket syntax)
  hq '*[select(.name == "x")]' file.tf --value

  # String functions (jq-compatible)
  hq 'module~[select(.source | contains("docker"))]' dir/
  hq 'resource~[select(.ami | test("^ami-"))]' dir/
  hq 'resource~[select(has("tags"))]' main.tf
  hq 'resource~[select(.tags | not)]' main.tf

  # Object construction (jq-style)
  hq 'resource[*] | {type: .block_type, name: .name_labels}' main.tf --json

  # Optional (exit 0 on empty results)
  hq 'nonexistent?' file.tf --value

  # Raw output (strip quotes, ideal for shell piping)
  hq 'resource.aws_instance.main.ami' main.tf --raw

  # NDJSON (one JSON object per line, ideal for streaming)
  hq 'resource[*]' dir/ --ndjson

  # Source location metadata
  hq 'resource[*]' main.tf --json --with-location

  # Comments in output
  hq 'resource[*]' main.tf --json --with-comments

  # Structural diff
  hq file1.tf --diff file2.tf
  hq file1.tf --diff file2.tf --json

  # Hybrid (structural::eval)
  hq 'resource.aws_instance[*]::name_labels' main.tf
  hq 'variable[*]::block_type' variables.tf --value

  # Pure eval (-e)
  hq -e 'doc.blocks("variable")[0].attribute("default").value' variables.tf --json

  # Introspection
  hq --describe 'variable[*]' variables.tf
  hq --schema

docs: https://github.com/amplify-education/python-hcl2/tree/main/docs
"""


_EVAL_PREFIXES = tuple(f"{name}(" for name in sorted(_SAFE_CALLABLE_NAMES)) + ("doc",)


def _normalize_eval_expr(expr_part: str) -> str:
    """Normalize the eval expression after '::' for ergonomics."""
    stripped = expr_part.strip()
    if not stripped:
        return "_"
    if stripped.startswith("_"):
        return stripped
    if stripped.startswith("."):
        return "_" + stripped
    # Check if it starts with a known function/variable name
    if stripped.startswith(_EVAL_PREFIXES):
        return stripped
    return "_." + stripped


def _dispatch_query(
    query_str: str,
    is_eval: bool,
    doc_view: DocumentView,
    file_path: str = "",
) -> List[Any]:
    """Dispatch a query and return results."""
    if is_eval:
        result = safe_eval(query_str, {"doc": doc_view})
        if isinstance(result, list):
            return result
        return [result]

    # Hybrid mode: checked before pipeline since "::" is unambiguous
    if "::" in query_str:
        from hcl2.query.path import parse_path

        path_part, expr_part = query_str.split("::", 1)
        segments = parse_path(path_part)
        nodes = resolve_path(doc_view, segments)
        expr = _normalize_eval_expr(expr_part)
        return [safe_eval(expr, {"_": node, "doc": doc_view}) for node in nodes]

    # Structural mode: route through pipeline (handles pipes, builtins, select)
    stages = [classify_stage(s) for s in split_pipeline(query_str)]
    return execute_pipeline(doc_view, stages, file_path=file_path)


def _strip_dollar_wrap(text: str) -> str:
    """Strip ``${...}`` wrapping from a serialized expression string."""
    if text.startswith("${") and text.endswith("}"):
        return text[2:-1]
    return text


def _strip_quotes(text: str) -> str:
    """Strip surrounding quotes from a string value."""
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _rawify(value: Any) -> Any:
    """Recursively strip quotes and ${} wrapping from all string values."""
    if isinstance(value, str):
        return _strip_dollar_wrap(_strip_quotes(value))
    if isinstance(value, dict):
        return {k: _rawify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rawify(v) for v in value]
    return value


def _convert_for_json(
    value: Any,
    options: Optional[SerializationOptions] = None,
) -> Any:
    """Recursively convert NodeViews to dicts for JSON serialization."""
    if isinstance(value, NodeView):
        return value.to_dict(options=options)
    if isinstance(value, list):
        return [_convert_for_json(item, options=options) for item in value]
    return value


@dataclasses.dataclass
class OutputConfig:
    """Output mode configuration for hq results.

    All fields are primitives or dataclasses, ensuring picklability
    for ``multiprocessing.Pool`` workers.
    """

    output_json: bool = False
    output_value: bool = False
    output_raw: bool = False
    json_indent: Optional[int] = None
    ndjson: bool = False
    with_location: bool = False
    with_comments: bool = False
    no_filename: bool = False
    serialization_options: Optional[SerializationOptions] = None

    def format_result(self, result: Any) -> str:
        """Format a single result for output."""
        if self.output_json:
            return json.dumps(
                _convert_for_json(result, options=self.serialization_options),
                indent=self.json_indent,
                default=str,
            )

        if self.output_raw:
            if isinstance(result, NodeView):
                val = result.to_dict()
                if isinstance(val, str):
                    return _strip_dollar_wrap(_strip_quotes(val))
                # For dicts with a single key (e.g. attribute), extract the value
                if isinstance(val, dict) and len(val) == 1:
                    inner = next(iter(val.values()))
                    if isinstance(inner, str):
                        return _strip_dollar_wrap(_strip_quotes(inner))
                    return str(inner)
                return json.dumps(_rawify(val), default=str)
            if isinstance(result, dict):
                return json.dumps(_rawify(result), default=str)
            if isinstance(result, str):
                return _strip_dollar_wrap(_strip_quotes(result))
            return str(result)

        if self.output_value:
            if isinstance(result, NodeView):
                val = result.to_dict()
                # Auto-unwrap single-key dicts (e.g. AttributeView → inner value)
                if isinstance(val, dict) and len(val) == 1:
                    inner = next(iter(val.values()))
                    return _strip_dollar_wrap(str(inner))
                return _strip_dollar_wrap(str(val))
            if isinstance(result, str):
                return _strip_dollar_wrap(result)
            return str(result)

        # Default: HCL output
        if isinstance(result, NodeView):
            return result.to_hcl()
        if isinstance(result, list):
            return self.format_list(result)
        if isinstance(result, str):
            return _strip_dollar_wrap(result)
        return str(result)

    def format_list(self, items: list) -> str:
        """Format a list result (e.g. from hybrid mode returning a list)."""
        if self.output_json:
            converted = [
                _convert_for_json(item, options=self.serialization_options)
                for item in items
            ]
            return json.dumps(converted, indent=self.json_indent, default=str)
        parts = []
        for item in items:
            if isinstance(item, NodeView):
                parts.append(
                    item.to_hcl() if not self.output_value else str(item.to_dict())
                )
            else:
                parts.append(str(item))
        if not self.output_value:
            return "[" + ", ".join(parts) + "]"
        return "\n".join(parts)

    def format_output(self, results: List[Any]) -> str:
        """Format results for final output."""
        if self.output_json and len(results) > 1:
            items = [
                _convert_for_json(item, options=self.serialization_options)
                for item in results
            ]
            return json.dumps(items, indent=self.json_indent, default=str)

        parts = []
        for result in results:
            parts.append(self.format_result(result))
        return "\n".join(parts)


_EXIT_TO_ERROR_TYPE = {
    EXIT_IO_ERROR: "io_error",
    EXIT_PARSE_ERROR: "parse_error",
    EXIT_QUERY_ERROR: "query_error",
}


def _error(msg: str, use_json: bool, **extra) -> str:
    """Format an error message."""
    if use_json:
        data = {"error": extra.get("error_type", "error"), "message": msg}
        data.update(extra)
        return json.dumps(data)
    return f"Error: {msg}"


def _run_diff(
    file1: str, file2: str, use_json: bool, json_indent: Optional[int]
) -> int:
    """Run structural diff between two HCL files.

    Returns an exit code: 0 if files are identical, 1 if they differ.
    Exits directly on I/O or parse errors (matching ``diff(1)`` convention).
    """
    import hcl2
    from hcl2.query.diff import diff_dicts, format_diff_json, format_diff_text

    opts = SerializationOptions(
        with_comments=False, with_meta=False, explicit_blocks=True
    )
    for path in (file1, file2):
        if path == "-":
            continue
        if not os.path.isfile(path):
            print(
                _error(f"File not found: {path}", use_json, error_type="io_error"),
                file=sys.stderr,
            )
            sys.exit(EXIT_IO_ERROR)

    try:
        if file1 == "-":
            text1 = sys.stdin.read()
        else:
            with open(file1, encoding="utf-8") as f:
                text1 = f.read()
        if file2 == "-":
            text2 = sys.stdin.read()
        else:
            with open(file2, encoding="utf-8") as f:
                text2 = f.read()
    except (OSError, IOError) as exc:
        print(_error(str(exc), use_json, error_type="io_error"), file=sys.stderr)
        sys.exit(EXIT_IO_ERROR)

    try:
        dict1 = hcl2.loads(text1, serialization_options=opts)
        dict2 = hcl2.loads(text2, serialization_options=opts)
    except Exception as exc:  # pylint: disable=broad-except
        print(_error(str(exc), use_json, error_type="parse_error"), file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    entries = diff_dicts(dict1, dict2)
    if not entries:
        return EXIT_SUCCESS

    if use_json:
        print(format_diff_json(entries))
    else:
        print(format_diff_text(entries))
    return EXIT_NO_RESULTS


_HCL_EXTENSIONS = {".tf", ".hcl", ".tfvars"}


def _collect_files(path: str) -> List[str]:
    """Return a list of HCL file paths from a file path, directory, or stdin marker."""
    if path == "-":
        return ["-"]
    if os.path.isdir(path):
        files = []
        for dirpath, _, filenames in os.walk(path):
            for fname in sorted(filenames):
                if os.path.splitext(fname)[1] in _HCL_EXTENSIONS:
                    files.append(os.path.join(dirpath, fname))
        files.sort()
        return files
    return [path]


# _expand_file_args is imported from .helpers and re-exported at module level.


def _run_query_on_file(
    file_path: str,
    query: str,
    is_eval: bool,
    use_json: bool,
    raw_query: str,
) -> Tuple[Optional[List[Any]], int]:
    """Parse a file and run a query.

    Returns ``(results, exit_code)``.  On error, results is ``None`` and
    exit_code is one of the ``EXIT_*`` constants.
    """
    try:
        if file_path == "-":
            text = sys.stdin.read()
        else:
            with open(file_path, encoding="utf-8") as f:
                text = f.read()
    except (OSError, IOError) as exc:
        print(_error(str(exc), use_json, error_type="io_error"), file=sys.stderr)
        return None, EXIT_IO_ERROR

    try:
        doc = DocumentView.parse(text)
    except Exception as exc:  # pylint: disable=broad-except
        print(
            _error(str(exc), use_json, error_type="parse_error", file=file_path),
            file=sys.stderr,
        )
        return None, EXIT_PARSE_ERROR

    try:
        return _dispatch_query(query, is_eval, doc, file_path=file_path), EXIT_SUCCESS
    except QuerySyntaxError as exc:
        print(
            _error(str(exc), use_json, error_type="query_syntax", query=raw_query),
            file=sys.stderr,
        )
        return None, EXIT_QUERY_ERROR
    except UnsafeExpressionError as exc:
        print(
            _error(
                str(exc),
                use_json,
                error_type="unsafe_expression",
                expression=raw_query,
            ),
            file=sys.stderr,
        )
        return None, EXIT_QUERY_ERROR
    except Exception as exc:  # pylint: disable=broad-except
        print(
            _error(str(exc), use_json, error_type="eval_error", query=raw_query),
            file=sys.stderr,
        )
        return None, EXIT_QUERY_ERROR


def _inject_provenance(converted: Any, file_path: str) -> Any:
    """Add ``__file__`` key to dict results for multi-file provenance."""
    if isinstance(converted, dict):
        return {"__file__": file_path, **converted}
    return converted


def _extract_location(result: Any, file_path: str) -> dict:
    """Extract source location metadata from a result."""
    from hcl2.query.pipeline import _LocatedDict

    loc: dict = {"__file__": file_path}
    meta = None
    if isinstance(result, NodeView):
        meta = getattr(result.raw, "_meta", None)
    elif isinstance(result, _LocatedDict):
        meta = result._source_meta
    if meta is not None:
        if hasattr(meta, "line"):
            loc["__line__"] = meta.line
        if hasattr(meta, "end_line"):
            loc["__end_line__"] = meta.end_line
        if hasattr(meta, "column"):
            loc["__column__"] = meta.column
        if hasattr(meta, "end_column"):
            loc["__end_column__"] = meta.end_column
    return loc


def _merge_location(converted: Any, location: dict) -> Any:
    """Merge location metadata into a converted JSON value."""
    if isinstance(converted, dict):
        return {**location, **converted}
    return {"__value__": converted, **location}


def _convert_results(
    results: List[Any],
    file_path: str,
    multi: bool,
    output_config: OutputConfig,
) -> List[Any]:
    """Convert query results for JSON output with location/provenance metadata."""
    converted = []
    for result in results:
        item = _convert_for_json(result, options=output_config.serialization_options)
        if output_config.with_location:
            loc = _extract_location(result, file_path)
            item = _merge_location(item, loc)
        elif multi and not output_config.no_filename:
            item = _inject_provenance(item, file_path)
        converted.append(item)
    return converted


def _process_file(args_tuple):
    """Worker: parse, query, and convert results for one file.

    Returns ``(file_path, exit_code, converted_results, error_msg)``.
    All return values are picklable plain Python objects.
    """
    file_path, query, is_eval, raw_query, multi, output_config = args_tuple

    try:
        with open(file_path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, IOError) as exc:
        return (file_path, EXIT_IO_ERROR, None, str(exc))

    try:
        doc = DocumentView.parse(text)
    except Exception as exc:  # pylint: disable=broad-except
        return (file_path, EXIT_PARSE_ERROR, None, str(exc))

    try:
        results = _dispatch_query(query, is_eval, doc, file_path=file_path)
    except (QuerySyntaxError, UnsafeExpressionError) as exc:
        return (file_path, EXIT_QUERY_ERROR, None, str(exc))
    except Exception as exc:  # pylint: disable=broad-except
        return (file_path, EXIT_QUERY_ERROR, None, str(exc))

    if not results:
        return (file_path, EXIT_SUCCESS, [], None)

    converted = _convert_results(results, file_path, multi, output_config)

    return (file_path, EXIT_SUCCESS, converted, None)


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``hq``."""
    parser = argparse.ArgumentParser(
        prog="hq",
        description=(
            "Query HCL2 files using jq-like structural paths. "
            "Supports pipes, select(), string functions, object construction. "
            "Prefer structural queries over -e (eval) mode."
        ),
        epilog=EXAMPLES_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "QUERY",
        nargs="?",
        default=None,
        help="Structural path, hybrid path::expr, or -e for eval",
    )
    parser.add_argument(
        "FILE",
        nargs="*",
        default=["-"],
        help="HCL2 files or directories (default: stdin)",
    )
    parser.add_argument(
        "-e",
        "--eval",
        action="store_true",
        help="Treat QUERY as a Python expression (doc bound to DocumentView)",
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Output as JSON")
    output_group.add_argument(
        "--value", action="store_true", help="Output raw value only"
    )
    output_group.add_argument(
        "--raw",
        action="store_true",
        help="Output raw string (strip surrounding quotes)",
    )

    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="Output one JSON object per line (newline-delimited JSON)",
    )
    parser.add_argument(
        "--json-indent",
        type=int,
        default=None,
        metavar="N",
        help="JSON indentation width (default: 2 for TTY, compact otherwise)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Show type and available properties/methods for query results",
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Dump full view API schema as JSON (ignores QUERY/FILE)",
    )
    parser.add_argument(
        "--no-filename",
        action="store_true",
        help="Suppress filename prefix when querying directories",
    )
    parser.add_argument(
        "--diff",
        metavar="FILE2",
        help="Structural diff against FILE2",
    )
    parser.add_argument(
        "--with-location",
        action="store_true",
        help="Include source file and line numbers in JSON output",
    )
    parser.add_argument(
        "--with-comments",
        action="store_true",
        help="Include comments in JSON output",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        metavar="N",
        help="Parallel workers (default: auto for large file sets, 0 or 1 = serial)",
    )
    return parser


def _validate_and_configure(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> Tuple[bool, OutputConfig]:
    """Validate argument combinations and build output configuration."""
    if args.ndjson:
        if args.value:
            parser.error("--ndjson cannot be combined with --value")
        if args.raw:
            parser.error("--ndjson cannot be combined with --raw")

    use_json = args.json or args.describe or args.schema or args.ndjson
    output_raw = getattr(args, "raw", False)

    # Resolve JSON indent: explicit flag > TTY default (2) > compact (None)
    if args.json_indent is not None:
        json_indent: Optional[int] = args.json_indent
    elif sys.stdout.isatty():
        json_indent = 2
    else:
        json_indent = None

    if args.with_location and not use_json:
        parser.error("--with-location requires --json or --ndjson")
    if args.with_comments and not use_json:
        parser.error("--with-comments requires --json or --ndjson")

    serialization_options = None
    if args.with_comments:
        serialization_options = SerializationOptions(with_comments=True)

    output_config = OutputConfig(
        output_json=args.json,
        output_value=args.value,
        output_raw=output_raw,
        json_indent=json_indent,
        ndjson=args.ndjson,
        with_location=args.with_location,
        with_comments=args.with_comments,
        no_filename=args.no_filename,
        serialization_options=serialization_options,
    )
    return use_json, output_config


def _resolve_query(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    use_json: bool,
    output_config: OutputConfig,
) -> Tuple[str, bool]:
    """Handle early exits and resolve the query string.

    May call ``sys.exit`` for ``--schema``/``--diff`` or ``parser.error``
    for invalid arguments and never return.  Otherwise returns
    ``(query, optional)``.
    """
    # --schema: dump schema and exit
    if args.schema:
        print(json.dumps(build_schema(), indent=2))
        sys.exit(EXIT_SUCCESS)

    # --diff: structural diff mode
    if args.diff:
        file1 = args.QUERY
        if file1 is None:
            parser.error("--diff requires two files: hq FILE1 --diff FILE2")
        sys.exit(_run_diff(file1, args.diff, use_json, output_config.json_indent))

    # QUERY is required unless --schema or --diff
    if args.QUERY is None:
        parser.error("the following arguments are required: QUERY")

    # Detect common mistake: user passed a file path but no query.
    if (
        args.FILE == ["-"]
        and sys.stdin.isatty()
        and args.QUERY
        and (os.path.exists(args.QUERY) or os.sep in args.QUERY)
    ):
        parser.error(f"missing QUERY argument (did you mean: hq QUERY {args.QUERY}?)")

    # Handle trailing '?' (optional operator — exit 0 on empty results)
    query = args.QUERY
    optional = query.rstrip().endswith("?") and not args.eval
    if optional:
        query = query.rstrip()[:-1].rstrip()

    return query, optional


def _emit_file_results(
    results: List[Any],
    file_path: str,
    multi: bool,
    output_config: OutputConfig,
    json_accumulator: List[Any],
) -> None:
    """Format and emit query results for one file."""
    # NDJSON mode: one JSON object per line (streaming, no accumulation)
    if output_config.ndjson:
        items = _convert_results(results, file_path, multi, output_config)
        for item in items:
            line = json.dumps(item, default=str)
            if (
                multi
                and not output_config.no_filename
                and not output_config.with_location
            ):
                # provenance already injected into dict; for non-dicts
                # prefix with filename
                if not isinstance(item, dict):
                    line = f"{file_path}:{line}"
            print(line, flush=True)
        return

    # JSON mode with multiple files: accumulate for merged output
    if output_config.output_json and multi:
        json_accumulator.extend(
            _convert_results(results, file_path, multi, output_config)
        )
        return

    # Single-file JSON with location
    if output_config.with_location:
        items = _convert_results(results, file_path, multi, output_config)
        data = items[0] if len(items) == 1 else items
        output = json.dumps(data, indent=output_config.json_indent, default=str)
    else:
        output = output_config.format_output(results)

    if multi and not output_config.no_filename and not output_config.with_location:
        prefix = f"{file_path}:"
        print("\n".join(prefix + line for line in output.splitlines()))
    else:
        print(output)


def _execute_and_emit(  # pylint: disable=too-many-branches
    args: argparse.Namespace,
    query: str,
    optional: bool,
    use_json: bool,
    output_config: OutputConfig,
) -> int:
    """Execute queries across files and emit results. Returns an exit code."""
    expanded_args = _expand_file_args(args.FILE)
    file_paths: List[str] = []
    for file_arg in expanded_args:
        file_paths.extend(_collect_files(file_arg))

    any_results = False
    worst_exit = EXIT_SUCCESS
    json_accumulator: List[Any] = []
    multi = len(file_paths) > 1

    # Decide whether to use parallel processing
    use_parallel = (
        multi
        and len(file_paths) >= 20
        and "-" not in file_paths
        and not args.eval
        and not args.describe
        and (args.json or args.ndjson)
        and (args.jobs is None or args.jobs > 1)
    )
    if args.jobs is not None and args.jobs <= 1:
        use_parallel = False

    if use_parallel:
        n_workers = args.jobs or min(os.cpu_count() or 1, len(file_paths))
        worker_args = [
            (fp, query, False, args.QUERY, multi, output_config) for fp in file_paths
        ]

        with multiprocessing.Pool(n_workers) as pool:
            for file_path, exit_code, converted, error_msg in pool.imap_unordered(
                _process_file, worker_args
            ):
                if error_msg:
                    etype = _EXIT_TO_ERROR_TYPE.get(exit_code, "error")
                    print(
                        _error(error_msg, use_json, error_type=etype),
                        file=sys.stderr,
                    )
                    worst_exit = max(worst_exit, exit_code)
                    continue
                if not converted:
                    continue
                any_results = True

                if args.ndjson:
                    for item in converted:
                        print(json.dumps(item, default=str), flush=True)
                elif args.json and multi:
                    json_accumulator.extend(converted)
    else:
        for file_path in file_paths:
            results, exit_code = _run_query_on_file(
                file_path, query, args.eval, use_json, args.QUERY
            )
            if results is None:
                worst_exit = max(worst_exit, exit_code)
                continue  # parse/query error already printed
            if not results:
                continue
            any_results = True

            if args.describe:
                print(json.dumps(describe_results(results), indent=2))
                continue

            _emit_file_results(
                results, file_path, multi, output_config, json_accumulator
            )

    # Emit accumulated JSON results as a single merged array
    if json_accumulator:
        # Sort by __file__ for deterministic output (parallel uses imap_unordered)
        json_accumulator.sort(
            key=lambda x: x.get("__file__", "") if isinstance(x, dict) else ""
        )
        print(
            json.dumps(json_accumulator, indent=output_config.json_indent, default=str)
        )

    if any_results:
        return EXIT_SUCCESS
    return EXIT_SUCCESS if optional else worst_exit or EXIT_NO_RESULTS


def main():
    """The ``hq`` console_scripts entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    use_json, output_config = _validate_and_configure(parser, args)
    query, optional = _resolve_query(args, parser, use_json, output_config)
    sys.exit(_execute_and_emit(args, query, optional, use_json, output_config))


if __name__ == "__main__":
    main()
