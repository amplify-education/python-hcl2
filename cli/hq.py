"""``hq`` CLI entry point — query HCL2 files."""

import argparse
import json
import os
import sys
from typing import Any, List

from hcl2.query._base import NodeView
from hcl2.query.body import DocumentView
from hcl2.query.introspect import build_schema, describe_results
from hcl2.query.path import QuerySyntaxError
from hcl2.query.pipeline import classify_stage, execute_pipeline, split_pipeline
from hcl2.query.resolver import resolve_path
from hcl2.query.safe_eval import UnsafeExpressionError, safe_eval
from hcl2.version import __version__

EXAMPLES_TEXT = """\
examples:
  # Structural queries
  hq 'resource.aws_instance.main.ami' main.tf
  hq 'variable[*]' variables.tf --json
  echo 'x = 1' | hq 'x' --value

  # Pipes
  hq 'resource[*] | .aws_instance | .tags' main.tf
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
    for prefix in (
        "len(",
        "str(",
        "int(",
        "float(",
        "bool(",
        "list(",
        "tuple(",
        "sorted(",
        "reversed(",
        "enumerate(",
        "zip(",
        "range(",
        "min(",
        "max(",
        "print(",
        "any(",
        "all(",
        "filter(",
        "map(",
        "isinstance(",
        "type(",
        "hasattr(",
        "getattr(",
        "doc",
    ):
        if stripped.startswith(prefix):
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


def _format_result(
    result: Any,
    output_json: bool,
    output_value: bool,
    json_indent: int,
    output_raw: bool = False,
) -> str:
    """Format a single result for output."""
    if output_json:
        return json.dumps(_convert_for_json(result), indent=json_indent, default=str)

    if output_raw:
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

    if output_value:
        if isinstance(result, NodeView):
            return _strip_dollar_wrap(str(result.to_dict()))
        if isinstance(result, str):
            return _strip_dollar_wrap(result)
        return str(result)

    # Default: HCL output
    if isinstance(result, NodeView):
        return result.to_hcl()
    if isinstance(result, list):
        return _format_list(result, output_json, output_value, json_indent, output_raw)
    if isinstance(result, str):
        return _strip_dollar_wrap(result)
    return str(result)


def _format_list(
    items: list,
    output_json: bool,
    output_value: bool,
    json_indent: int,
    output_raw: bool = False,
) -> str:
    """Format a list result (e.g. from hybrid mode returning a list property)."""
    if output_json:
        converted = [
            item.to_dict() if isinstance(item, NodeView) else item for item in items
        ]
        return json.dumps(converted, indent=json_indent, default=str)
    parts = []
    for item in items:
        if isinstance(item, NodeView):
            parts.append(item.to_hcl() if not output_value else str(item.to_dict()))
        else:
            parts.append(str(item))
    return "[" + ", ".join(parts) + "]" if not output_value else "\n".join(parts)


def _convert_for_json(value: Any) -> Any:
    """Recursively convert NodeViews to dicts for JSON serialization."""
    if isinstance(value, NodeView):
        return value.to_dict()
    if isinstance(value, list):
        return [_convert_for_json(item) for item in value]
    return value


def _format_output(
    results: List[Any],
    output_json: bool,
    output_value: bool,
    json_indent: int,
    output_raw: bool = False,
) -> str:
    """Format results for final output."""
    if output_json and len(results) > 1:
        items = [_convert_for_json(item) for item in results]
        return json.dumps(items, indent=json_indent, default=str)

    parts = []
    for result in results:
        parts.append(
            _format_result(result, output_json, output_value, json_indent, output_raw)
        )
    return "\n".join(parts)


def _error(msg: str, use_json: bool, **extra) -> str:
    """Format an error message."""
    if use_json:
        data = {"error": extra.get("error_type", "error"), "message": msg}
        data.update(extra)
        return json.dumps(data)
    return f"Error: {msg}"


def _run_diff(file1: str, file2: str, use_json: bool, json_indent: int) -> None:
    """Run structural diff between two HCL files."""
    import hcl2
    from hcl2.query.diff import diff_dicts, format_diff_json, format_diff_text
    from hcl2.utils import SerializationOptions

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
            sys.exit(1)

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
        sys.exit(1)

    try:
        dict1 = hcl2.loads(text1, serialization_options=opts)
        dict2 = hcl2.loads(text2, serialization_options=opts)
    except Exception as exc:  # pylint: disable=broad-except
        print(_error(str(exc), use_json, error_type="parse_error"), file=sys.stderr)
        sys.exit(1)

    entries = diff_dicts(dict1, dict2)
    if not entries:
        sys.exit(0)

    if use_json:
        print(format_diff_json(entries))
    else:
        print(format_diff_text(entries))


def _find_file_keys(query: str) -> List[str]:
    """Find construct output keys that reference ``__file__``.

    Handles both shorthand ``{__file__}`` (key="__file__") and
    renamed ``{file: .__file__}`` (key="file").
    """
    import re

    keys: List[str] = []
    # Match renamed: "key: .__file__" or "key: __file__"
    for m in re.finditer(r"(\w+)\s*:\s*\.?__file__", query):
        keys.append(m.group(1))
    # Match shorthand: bare "__file__" as a construct field (not after ":")
    if re.search(r"(?<![:\w])\.?__file__(?!\s*:)", query):
        keys.append("__file__")
    return keys


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


def _run_query_on_file(
    file_path: str,
    query: str,
    is_eval: bool,
    use_json: bool,
    raw_query: str,
) -> "List[Any] | None":
    """Parse a file and run a query. Returns results or None on error."""
    try:
        if file_path == "-":
            text = sys.stdin.read()
        else:
            with open(file_path, encoding="utf-8") as f:
                text = f.read()
    except (OSError, IOError) as exc:
        print(_error(str(exc), use_json, error_type="io_error"), file=sys.stderr)
        return None

    try:
        doc = DocumentView.parse(text)
    except Exception as exc:  # pylint: disable=broad-except
        print(
            _error(str(exc), use_json, error_type="parse_error", file=file_path),
            file=sys.stderr,
        )
        return None

    try:
        return _dispatch_query(query, is_eval, doc, file_path=file_path)
    except QuerySyntaxError as exc:
        print(
            _error(str(exc), use_json, error_type="query_syntax", query=raw_query),
            file=sys.stderr,
        )
        return None
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
        return None
    except Exception as exc:  # pylint: disable=broad-except
        print(
            _error(str(exc), use_json, error_type="eval_error", query=raw_query),
            file=sys.stderr,
        )
        return None


def main():
    """The ``hq`` console_scripts entry point."""
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
        nargs="?",
        default="-",
        help="HCL2 file (default: stdin)",
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
        "--json-indent",
        type=int,
        default=2,
        metavar="N",
        help="JSON indentation width (default: 2)",
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

    args = parser.parse_args()
    use_json = args.json or args.describe or args.schema
    output_raw = getattr(args, "raw", False)

    # --schema: dump schema and exit
    if args.schema:
        print(json.dumps(build_schema(), indent=2))
        sys.exit(0)

    # --diff: structural diff mode
    # Usage: hq FILE1 --diff FILE2  (FILE1 is the first positional arg)
    if args.diff:
        file1 = args.QUERY
        if file1 is None:
            parser.error("--diff requires two files: hq FILE1 --diff FILE2")
        _run_diff(file1, args.diff, use_json, args.json_indent)
        sys.exit(0)

    # QUERY is required unless --schema or --diff
    if args.QUERY is None:
        parser.error("the following arguments are required: QUERY")

    # Detect common mistake: user passed a file path but no query.
    # When only one positional arg is given, argparse puts it in QUERY
    # and FILE defaults to stdin.  If stdin is a TTY (not piped) and
    # QUERY looks like a file/directory path, give a helpful error
    # instead of hanging on stdin.
    if (
        args.FILE == "-"
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

    # Collect input files
    file_paths = _collect_files(args.FILE)

    any_results = False
    for file_path in file_paths:
        multi = len(file_paths) > 1
        results = _run_query_on_file(file_path, query, args.eval, use_json, args.QUERY)
        if results is None:
            continue  # parse/query error already printed
        if not results:
            continue
        any_results = True

        if args.describe:
            print(json.dumps(describe_results(results), indent=2))
            continue

        output = _format_output(
            results, args.json, args.value, args.json_indent, output_raw
        )
        if multi and not args.no_filename:
            prefix = f"{file_path}:"
            print("\n".join(prefix + line for line in output.splitlines()))
        else:
            print(output)

    if not any_results:
        sys.exit(0 if optional else 1)
    sys.exit(0)


if __name__ == "__main__":
    main()
