"""``jsontohcl2`` CLI entry point — convert JSON files to HCL2."""

import argparse
import difflib
import json
import os
import sys
from io import StringIO
from typing import TextIO

from hcl2 import dump
from hcl2.deserializer import DeserializerOptions
from hcl2.formatter import FormatterOptions
from hcl2.version import __version__
from .helpers import (
    EXIT_DIFF,
    EXIT_IO_ERROR,
    EXIT_PARSE_ERROR,
    EXIT_PARTIAL,
    JSON_SKIPPABLE,  # used in _convert_* calls for skip handling
    _convert_directory,
    _convert_multiple_files,
    _convert_single_file,
    _convert_stdin,
    _error,
    _expand_file_args,
)


def _json_to_hcl(
    in_file: TextIO,
    out_file: TextIO,
    d_opts: DeserializerOptions,
    f_opts: FormatterOptions,
) -> None:
    data = json.load(in_file)
    dump(data, out_file, deserializer_options=d_opts, formatter_options=f_opts)


def _json_to_hcl_string(
    in_file: TextIO,
    d_opts: DeserializerOptions,
    f_opts: FormatterOptions,
) -> str:
    """Convert JSON input to an HCL string (for --diff / --dry-run)."""
    buf = StringIO()
    _json_to_hcl(in_file, buf, d_opts, f_opts)
    return buf.getvalue()


def _json_to_hcl_fragment(
    in_file: TextIO,
    d_opts: DeserializerOptions,
    f_opts: FormatterOptions,
) -> str:
    """Convert a JSON fragment to HCL attribute assignments.

    Unlike normal conversion, this strips ``__is_block__`` markers so the
    input is always treated as flat attributes — even if it came from
    ``hcl2tojson`` output.
    """
    data = json.load(in_file)
    if not isinstance(data, dict):
        raise TypeError(f"--fragment expects a JSON object, got {type(data).__name__}")
    data = _strip_block_markers(data)
    buf = StringIO()
    dump(data, buf, deserializer_options=d_opts, formatter_options=f_opts)
    return buf.getvalue()


def _strip_block_markers(data):
    """Recursively remove ``__is_block__`` keys from nested dicts."""
    if isinstance(data, dict):
        return {
            k: _strip_block_markers(v) for k, v in data.items() if k != "__is_block__"
        }
    if isinstance(data, list):
        return [_strip_block_markers(item) for item in data]
    return data


_EXAMPLES = """\
examples:
  jsontohcl2 file.json                          # single file to stdout
  jsontohcl2 a.json b.json -o out/             # multiple files to output dir
  jsontohcl2 --diff original.tf modified.json  # preview changes
  jsontohcl2 --dry-run file.json               # convert without writing
  jsontohcl2 --fragment -                       # attribute snippet from stdin
  echo '{"x": 1}' | jsontohcl2                 # stdin (no args needed)

exit codes:
  0  Success
  1  JSON parse error
  2  Valid JSON but incompatible HCL structure
  4  I/O error (file not found)
  5  Differences found (--diff mode only)
"""


def main():  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    """The ``jsontohcl2`` console_scripts entry point."""
    parser = argparse.ArgumentParser(
        description="Convert JSON files to HCL2",
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
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--diff",
        metavar="ORIGINAL",
        help="Show unified diff against ORIGINAL file instead of writing output",
    )
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Convert and print to stdout without writing files",
    )
    mode_group.add_argument(
        "--fragment",
        action="store_true",
        help="Treat input as a JSON fragment (attribute dict, not full HCL document)",
    )
    parser.add_argument("--version", action="version", version=__version__)

    # DeserializerOptions flags
    parser.add_argument(
        "--colon-separator",
        action="store_true",
        help="Use colons instead of equals in object elements",
    )
    parser.add_argument(
        "--no-trailing-comma",
        action="store_true",
        help="Omit trailing commas in object elements",
    )
    parser.add_argument(
        "--heredocs-to-strings",
        action="store_true",
        help="Convert heredocs to plain strings",
    )
    parser.add_argument(
        "--strings-to-heredocs",
        action="store_true",
        help="Convert strings containing escaped newlines to heredocs",
    )

    # FormatterOptions flags
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        metavar="N",
        help="Indentation width (default: 2)",
    )
    parser.add_argument(
        "--no-open-empty-blocks",
        action="store_true",
        help="Collapse empty blocks to a single line",
    )
    parser.add_argument(
        "--no-open-empty-objects",
        action="store_true",
        help="Collapse empty objects to a single line",
    )
    parser.add_argument(
        "--open-empty-tuples",
        action="store_true",
        help="Expand empty tuples across multiple lines",
    )
    parser.add_argument(
        "--no-align",
        action="store_true",
        help="Disable vertical alignment of attributes and object elements",
    )

    args = parser.parse_args()

    d_opts = DeserializerOptions(
        object_elements_colon=args.colon_separator,
        object_elements_trailing_comma=not args.no_trailing_comma,
        heredocs_to_strings=args.heredocs_to_strings,
        strings_to_heredocs=args.strings_to_heredocs,
    )
    f_opts = FormatterOptions(
        indent_length=args.indent,
        open_empty_blocks=not args.no_open_empty_blocks,
        open_empty_objects=not args.no_open_empty_objects,
        open_empty_tuples=args.open_empty_tuples,
        vertically_align_attributes=not args.no_align,
        vertically_align_object_elements=not args.no_align,
    )
    quiet = args.quiet

    def convert(in_file, out_file):
        _json_to_hcl(in_file, out_file, d_opts, f_opts)

    # Default to stdin when no paths given
    paths = args.PATH if args.PATH else ["-"]
    paths = _expand_file_args(paths)
    output = args.output

    try:
        # --diff mode: convert JSON, diff against original file
        if args.diff:
            if len(paths) != 1:
                parser.error("--diff requires exactly one input file")
            json_path = paths[0]
            original_path = args.diff

            if not os.path.isfile(original_path):
                print(
                    _error(
                        f"File not found: {original_path}",
                        error_type="io_error",
                        file=original_path,
                    ),
                    file=sys.stderr,
                )
                sys.exit(EXIT_IO_ERROR)

            if json_path == "-":
                hcl_output = _json_to_hcl_string(sys.stdin, d_opts, f_opts)
            else:
                with open(json_path, "r", encoding="utf-8") as f:
                    hcl_output = _json_to_hcl_string(f, d_opts, f_opts)

            with open(original_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            converted_lines = hcl_output.splitlines(keepends=True)
            diff_output = list(
                difflib.unified_diff(
                    original_lines,
                    converted_lines,
                    fromfile=original_path,
                    tofile=f"(from {json_path})",
                )
            )
            if diff_output:
                sys.stdout.writelines(diff_output)
                sys.exit(EXIT_DIFF)
            return

        # --dry-run mode: convert to stdout without writing
        if args.dry_run:
            if len(paths) != 1:
                parser.error("--dry-run requires exactly one input file")
            json_path = paths[0]
            if json_path == "-":
                hcl_output = _json_to_hcl_string(sys.stdin, d_opts, f_opts)
            else:
                with open(json_path, "r", encoding="utf-8") as f:
                    hcl_output = _json_to_hcl_string(f, d_opts, f_opts)
            sys.stdout.write(hcl_output)
            return

        # --fragment mode: convert JSON fragment to HCL attributes
        if args.fragment:
            if len(paths) != 1:
                parser.error("--fragment requires exactly one input file")
            json_path = paths[0]
            if json_path == "-":
                hcl_output = _json_to_hcl_fragment(sys.stdin, d_opts, f_opts)
            else:
                with open(json_path, "r", encoding="utf-8") as f:
                    hcl_output = _json_to_hcl_fragment(f, d_opts, f_opts)
            sys.stdout.write(hcl_output)
            return

        if len(paths) == 1:
            path = paths[0]
            if path == "-":
                _convert_stdin(convert)
            elif os.path.isfile(path):
                _convert_single_file(
                    path, output, convert, args.skip, JSON_SKIPPABLE, quiet=quiet
                )
            elif os.path.isdir(path):
                if output is None:
                    parser.error("directory conversion requires -o <dir>")
                if _convert_directory(
                    path,
                    output,
                    convert,
                    args.skip,
                    JSON_SKIPPABLE,
                    in_extensions={".json"},
                    out_extension=".tf",
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
            any_skipped = False
            if output is None:
                for file_path in paths:
                    if not _convert_single_file(
                        file_path,
                        None,
                        convert,
                        args.skip,
                        JSON_SKIPPABLE,
                        quiet=quiet,
                    ):
                        any_skipped = True
            else:
                any_skipped = _convert_multiple_files(
                    paths,
                    output,
                    convert,
                    args.skip,
                    JSON_SKIPPABLE,
                    out_extension=".tf",
                    quiet=quiet,
                )
            if any_skipped:
                sys.exit(EXIT_PARTIAL)
    except json.JSONDecodeError as exc:
        print(
            _error(str(exc), error_type="json_parse_error"),
            file=sys.stderr,
        )
        sys.exit(EXIT_PARTIAL)
    except UnicodeDecodeError as exc:
        print(
            _error(str(exc), error_type="parse_error"),
            file=sys.stderr,
        )
        sys.exit(EXIT_PARTIAL)
    except (KeyError, TypeError, ValueError) as exc:
        print(
            _error(str(exc), error_type="structure_error"),
            file=sys.stderr,
        )
        sys.exit(EXIT_PARSE_ERROR)
    except (OSError, IOError) as exc:
        print(
            _error(str(exc), error_type="io_error"),
            file=sys.stderr,
        )
        sys.exit(EXIT_IO_ERROR)
