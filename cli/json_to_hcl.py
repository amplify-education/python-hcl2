"""``jsontohcl2`` CLI entry point — convert JSON files to HCL2."""

import argparse
import json
import os
from typing import TextIO

from hcl2 import dump
from hcl2.deserializer import DeserializerOptions
from hcl2.formatter import FormatterOptions
from hcl2.version import __version__
from .helpers import (
    JSON_SKIPPABLE,
    _convert_single_file,
    _convert_directory,
    _convert_multiple_files,
    _convert_stdin,
)


def _json_to_hcl(
    in_file: TextIO,
    out_file: TextIO,
    d_opts: DeserializerOptions,
    f_opts: FormatterOptions,
) -> None:
    data = json.load(in_file)
    dump(data, out_file, deserializer_options=d_opts, formatter_options=f_opts)


def main():
    """The ``jsontohcl2`` console_scripts entry point."""
    parser = argparse.ArgumentParser(
        description="Convert JSON files to HCL2",
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

    def convert(in_file, out_file):
        _json_to_hcl(in_file, out_file, d_opts, f_opts)

    paths = args.PATH
    output = args.output

    if len(paths) == 1:
        path = paths[0]
        if path == "-":
            _convert_stdin(convert)
        elif os.path.isfile(path):
            _convert_single_file(path, output, convert, args.skip, JSON_SKIPPABLE)
        elif os.path.isdir(path):
            _convert_directory(
                path,
                output,
                convert,
                args.skip,
                JSON_SKIPPABLE,
                in_extensions={".json"},
                out_extension=".tf",
            )
        else:
            raise RuntimeError(f"Invalid Path: {path}")
    else:
        for p in paths:
            if not os.path.isfile(p):
                raise RuntimeError(f"Invalid file: {p}")
        if output is None:
            for p in paths:
                _convert_single_file(p, None, convert, args.skip, JSON_SKIPPABLE)
        else:
            _convert_multiple_files(
                paths,
                output,
                convert,
                args.skip,
                JSON_SKIPPABLE,
                out_extension=".tf",
            )
