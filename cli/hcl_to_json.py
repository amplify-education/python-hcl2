"""``hcl2tojson`` CLI entry point — convert HCL2 files to JSON."""

import argparse
import json
import os
import sys
from typing import IO, List, Optional, TextIO

from hcl2 import load
from hcl2.utils import SerializationOptions
from hcl2.version import __version__
from .helpers import (
    EXIT_IO_ERROR,
    EXIT_PARSE_ERROR,
    EXIT_PARTIAL,
    EXIT_SUCCESS,
    HCL_SKIPPABLE,
    _collect_files,
    _convert_directory,
    _convert_multiple_files,
    _convert_single_file,
    _convert_stdin,
    _error,
    _expand_file_args,
)

_HCL_EXTENSIONS = {".tf", ".hcl"}


def _filter_data(
    data: dict,
    only: Optional[str] = None,
    exclude: Optional[str] = None,
    fields: Optional[str] = None,
) -> dict:
    """Apply block-type filtering and field projection to parsed HCL data."""
    if only:
        types = {t.strip() for t in only.split(",")}
        data = {k: val for k, val in data.items() if k in types}
    elif exclude:
        types = {t.strip() for t in exclude.split(",")}
        data = {k: val for k, val in data.items() if k not in types}
    if fields:
        field_set = {f.strip() for f in fields.split(",")}
        data = _project_fields(data, field_set)
    return data


def _project_fields(data, field_set):
    """Keep only specified fields (plus metadata keys) in nested dicts.

    Structural keys (whose values are dicts or lists) are always preserved
    so the block hierarchy stays intact.  Only leaf attribute keys are
    filtered.
    """
    if isinstance(data, dict):
        result = {}
        for key, val in data.items():
            if key in field_set or key.startswith("__"):
                result[key] = val
            elif isinstance(val, (dict, list)):
                projected = _project_fields(val, field_set)
                if projected:
                    result[key] = projected
            # else: leaf value not in field_set — drop it
        return result
    if isinstance(data, list):
        out = [_project_fields(item, field_set) for item in data]
        return [item for item in out if not isinstance(item, (dict, list)) or item]
    return data


def _hcl_to_json(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    in_file: TextIO,
    out_file: IO,
    options: SerializationOptions,
    json_indent: Optional[int] = None,
    only: Optional[str] = None,
    exclude: Optional[str] = None,
    fields: Optional[str] = None,
) -> None:
    data = load(in_file, serialization_options=options)
    data = _filter_data(data, only, exclude, fields)
    json.dump(data, out_file, indent=json_indent)


def _load_to_dict(
    in_file: TextIO,
    options: SerializationOptions,
    only: Optional[str] = None,
    exclude: Optional[str] = None,
    fields: Optional[str] = None,
) -> dict:
    """Load HCL2 and return the parsed dict (no JSON serialization)."""
    data = load(in_file, serialization_options=options)
    return _filter_data(data, only, exclude, fields)


def _stream_ndjson(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    file_paths: List[str],
    options: SerializationOptions,
    json_indent: Optional[int],
    skip: bool,
    quiet: bool,
    add_provenance: bool,
    only: Optional[str] = None,
    exclude: Optional[str] = None,
    fields: Optional[str] = None,
) -> int:
    """Stream one JSON object per file to stdout (NDJSON).

    Returns the worst exit code encountered.
    """
    worst_exit = EXIT_SUCCESS
    any_success = False
    for file_path in file_paths:
        if not quiet and file_path != "-":
            print(file_path, file=sys.stderr, flush=True)
        try:
            if file_path == "-":
                data = _load_to_dict(
                    sys.stdin, options, only=only, exclude=exclude, fields=fields
                )
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = _load_to_dict(
                        f, options, only=only, exclude=exclude, fields=fields
                    )
        except HCL_SKIPPABLE as exc:
            if skip:
                worst_exit = max(worst_exit, EXIT_PARTIAL)
                continue
            print(
                _error(
                    str(exc), use_json=True, error_type="parse_error", file=file_path
                ),
                file=sys.stderr,
            )
            return EXIT_PARSE_ERROR
        except (OSError, IOError) as exc:
            if skip:
                worst_exit = max(worst_exit, EXIT_PARTIAL)
                continue
            print(
                _error(str(exc), use_json=True, error_type="io_error", file=file_path),
                file=sys.stderr,
            )
            return EXIT_IO_ERROR

        if add_provenance:
            data = {"__file__": file_path, **data}
        print(json.dumps(data, indent=json_indent), flush=True)
        any_success = True

    if not any_success and worst_exit > EXIT_SUCCESS:
        return EXIT_PARSE_ERROR
    return worst_exit


_EXAMPLES = """\
examples:
  hcl2tojson file.tf                        # single file to stdout
  hcl2tojson --ndjson dir/                  # directory to stdout (NDJSON)
  hcl2tojson a.tf b.tf -o out/             # multiple files to output dir
  hcl2tojson --ndjson a.tf b.tf            # multiple files as NDJSON
  hcl2tojson --ndjson 'modules/**/*.tf'    # glob + NDJSON streaming
  hcl2tojson --only resource,module file.tf # block type filtering
  hcl2tojson --compact file.tf             # single-line JSON
  echo 'x = 1' | hcl2tojson               # stdin (no args needed)

exit codes:
  0  Success
  1  Partial success (some files skipped via -s)
  2  Parse error (all input unparsable)
  4  I/O error (file not found)
"""


def main():  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    """The ``hcl2tojson`` console_scripts entry point."""
    parser = argparse.ArgumentParser(
        description="Convert HCL2 files to JSON",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s", dest="skip", action="store_true", help="Skip un-parsable files"
    )
    parser.add_argument(
        "PATH",
        nargs="*",
        help="Files, directories, or glob patterns to convert (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Output path (file for single input, directory for multiple inputs)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output on stderr (errors still shown)",
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="Output one JSON object per line (newline-delimited JSON)",
    )
    parser.add_argument("--version", action="version", version=__version__)

    # SerializationOptions flags
    parser.add_argument(
        "--with-meta",
        action="store_true",
        help="Add meta parameters like __start_line__ and __end_line__",
    )
    parser.add_argument(
        "--with-comments",
        action="store_true",
        help="Include comments in the output",
    )
    parser.add_argument(
        "--wrap-objects",
        action="store_true",
        help="Wrap object values as an inline HCL2",
    )
    parser.add_argument(
        "--wrap-tuples",
        action="store_true",
        help="Wrap tuple values an inline HCL2",
    )
    parser.add_argument(
        "--no-explicit-blocks",
        action="store_true",
        help="Disable explicit block markers. Note: round-trip through json_to_hcl "
        "is NOT supported with this option.",
    )
    parser.add_argument(
        "--no-preserve-heredocs",
        action="store_true",
        help="Convert heredocs to plain strings",
    )
    parser.add_argument(
        "--force-parens",
        action="store_true",
        help="Force parentheses around all operations",
    )
    parser.add_argument(
        "--no-preserve-scientific",
        action="store_true",
        help="Convert scientific notation to standard floats",
    )
    parser.add_argument(
        "--strip-string-quotes",
        action="store_true",
        help="Strip surrounding double-quotes from serialized string values. "
        "Note: round-trip through json_to_hcl is NOT supported with this option.",
    )

    # JSON output formatting
    parser.add_argument(
        "--json-indent",
        type=int,
        default=None,
        metavar="N",
        help="JSON indentation width (default: 2 for TTY, compact otherwise)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact single-line JSON output (no indentation or newlines)",
    )

    # Filtering
    filter_group = parser.add_mutually_exclusive_group()
    filter_group.add_argument(
        "--only",
        metavar="TYPES",
        help="Comma-separated block types to include (e.g. resource,module)",
    )
    filter_group.add_argument(
        "--exclude",
        metavar="TYPES",
        help="Comma-separated block types to exclude (e.g. variable,output)",
    )
    parser.add_argument(
        "--fields",
        metavar="FIELDS",
        help="Comma-separated field names to keep in output",
    )

    args = parser.parse_args()

    options = SerializationOptions(
        with_meta=args.with_meta,
        with_comments=args.with_comments,
        wrap_objects=args.wrap_objects,
        wrap_tuples=args.wrap_tuples,
        explicit_blocks=not args.no_explicit_blocks,
        preserve_heredocs=not args.no_preserve_heredocs,
        force_operation_parentheses=args.force_parens,
        preserve_scientific_notation=not args.no_preserve_scientific,
        strip_string_quotes=args.strip_string_quotes,
    )

    # Resolve JSON indent: --compact > explicit --json-indent > TTY default (2) > compact
    if args.compact:
        json_indent: Optional[int] = None
    elif args.json_indent is not None:
        json_indent = args.json_indent
    elif sys.stdout.isatty():
        json_indent = 2
    else:
        json_indent = None

    quiet = args.quiet
    ndjson = args.ndjson
    only = args.only
    exclude = args.exclude
    fields = args.fields

    def convert(in_file, out_file):
        _hcl_to_json(
            in_file,
            out_file,
            options,
            json_indent=json_indent,
            only=only,
            exclude=exclude,
            fields=fields,
        )

    # Default to stdin when no paths given
    paths = args.PATH if args.PATH else ["-"]
    paths = _expand_file_args(paths)
    output = args.output

    try:
        # NDJSON streaming mode (explicit --ndjson flag)
        if ndjson:
            file_paths = _resolve_file_paths(paths, parser)
            if args.json_indent is not None and not quiet:
                print(
                    "Warning: --json-indent is ignored in NDJSON mode",
                    file=sys.stderr,
                )
            # NDJSON always uses compact output (one object per line)
            ndjson_indent = None
            exit_code = _stream_ndjson(
                file_paths,
                options,
                ndjson_indent,
                args.skip,
                quiet,
                add_provenance=len(file_paths) > 1,
                only=only,
                exclude=exclude,
                fields=fields,
            )
            if exit_code != EXIT_SUCCESS:
                sys.exit(exit_code)
            return

        if len(paths) == 1:
            path = paths[0]
            if path == "-":
                _convert_stdin(convert)
            elif os.path.isfile(path):
                _convert_single_file(
                    path, output, convert, args.skip, HCL_SKIPPABLE, quiet=quiet
                )
            elif os.path.isdir(path):
                if output is None:
                    parser.error("directory to stdout requires --ndjson or -o <dir>")
                if _convert_directory(
                    path,
                    output,
                    convert,
                    args.skip,
                    HCL_SKIPPABLE,
                    in_extensions=_HCL_EXTENSIONS,
                    out_extension=".json",
                    quiet=quiet,
                ):
                    sys.exit(EXIT_PARTIAL)
            else:
                print(
                    _error(
                        f"File not found: {path}",
                        error_type="io_error",
                        file=path,
                    ),
                    file=sys.stderr,
                )
                sys.exit(EXIT_IO_ERROR)
        else:
            # Validate all paths are files
            for file_path in paths:
                if not os.path.isfile(file_path):
                    print(
                        _error(
                            f"Invalid file: {file_path}",
                            error_type="io_error",
                            file=file_path,
                        ),
                        file=sys.stderr,
                    )
                    sys.exit(EXIT_IO_ERROR)
            if output is None:
                parser.error("multiple files to stdout requires --ndjson or -o <dir>")
            if _convert_multiple_files(
                paths,
                output,
                convert,
                args.skip,
                HCL_SKIPPABLE,
                out_extension=".json",
                quiet=quiet,
            ):
                sys.exit(EXIT_PARTIAL)
    except HCL_SKIPPABLE as exc:
        print(
            _error(str(exc), error_type="parse_error"),
            file=sys.stderr,
        )
        sys.exit(EXIT_PARSE_ERROR)
    except (OSError, IOError) as exc:
        print(
            _error(str(exc), error_type="io_error"),
            file=sys.stderr,
        )
        sys.exit(EXIT_IO_ERROR)


def _resolve_file_paths(paths: List[str], parser) -> List[str]:
    """Expand directories into individual file paths for NDJSON streaming."""
    file_paths: List[str] = []
    for path in paths:
        file_paths.extend(_collect_files(path, _HCL_EXTENSIONS))
    if not file_paths:
        parser.error("no HCL files found in the given paths")
    return file_paths
