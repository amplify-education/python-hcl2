"""``hcl2tojson`` CLI entry point — convert HCL2 files to JSON."""

import argparse
import json
import os
from typing import IO, Optional, TextIO

from hcl2 import load
from hcl2.utils import SerializationOptions
from hcl2.version import __version__
from .helpers import (
    HCL_SKIPPABLE,
    _convert_single_file,
    _convert_directory,
    _convert_multiple_files,
    _convert_stdin,
)


def _hcl_to_json(
    in_file: TextIO,
    out_file: IO,
    options: SerializationOptions,
    json_indent: Optional[int] = None,
) -> None:
    data = load(in_file, serialization_options=options)
    json.dump(data, out_file, indent=json_indent)


def main():
    """The ``hcl2tojson`` console_scripts entry point."""
    parser = argparse.ArgumentParser(
        description="Convert HCL2 files to JSON",
    )
    parser.add_argument(
        "-s", dest="skip", action="store_true", help="Skip un-parsable files"
    )
    parser.add_argument(
        "PATH",
        nargs="+",
        help='One or more files or directories to convert (use "-" for stdin)',
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        help="Output path (file for single input, directory for multiple inputs)",
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
        help="Disable explicit block markers. Note: round-trip through json_to_hcl is NOT supported with this option.",
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
        help="Strip surrounding double-quotes from serialized string values. Note: round-trip through json_to_hcl is NOT supported with this option.",
    )

    # JSON output formatting
    parser.add_argument(
        "--json-indent",
        type=int,
        default=2,
        metavar="N",
        help="JSON indentation width (default: 2)",
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
    json_indent = args.json_indent

    def convert(in_file, out_file):
        _hcl_to_json(in_file, out_file, options, json_indent=json_indent)

    paths = args.PATH
    output = args.output

    if len(paths) == 1:
        path = paths[0]
        if path == "-":
            _convert_stdin(convert)
        elif os.path.isfile(path):
            _convert_single_file(path, output, convert, args.skip, HCL_SKIPPABLE)
        elif os.path.isdir(path):
            _convert_directory(
                path,
                output,
                convert,
                args.skip,
                HCL_SKIPPABLE,
                in_extensions={".tf", ".hcl"},
                out_extension=".json",
            )
        else:
            raise RuntimeError(f"Invalid Path: {path}")
    else:
        for p in paths:
            if not os.path.isfile(p):
                raise RuntimeError(f"Invalid file: {p}")
        if output is None:
            for p in paths:
                _convert_single_file(p, None, convert, args.skip, HCL_SKIPPABLE)
        else:
            _convert_multiple_files(
                paths,
                output,
                convert,
                args.skip,
                HCL_SKIPPABLE,
                out_extension=".json",
            )
