"""Shared file-conversion helpers for the HCL2 CLI commands."""
import json
import os
import sys
from typing import Callable, IO, Set, Tuple, Type

from lark import UnexpectedCharacters, UnexpectedToken

# Exceptions that can be skipped when -s is passed
HCL_SKIPPABLE = (UnexpectedToken, UnexpectedCharacters, UnicodeDecodeError)
JSON_SKIPPABLE = (json.JSONDecodeError, UnicodeDecodeError)


def _convert_single_file(
    in_path: str,
    out_path: str,
    convert_fn: Callable[[IO, IO], None],
    skip: bool,
    skippable: Tuple[Type[BaseException], ...],
) -> None:
    with open(in_path, "r", encoding="utf-8") as in_file:
        print(in_path, file=sys.stderr, flush=True)
        if out_path is not None:
            try:
                with open(out_path, "w", encoding="utf-8") as out_file:
                    convert_fn(in_file, out_file)
            except skippable:
                if skip:
                    return
                raise
        else:
            try:
                convert_fn(in_file, sys.stdout)
                sys.stdout.write("\n")
            except skippable:
                if skip:
                    return
                raise


def _convert_directory(
    in_path: str,
    out_path: str,
    convert_fn: Callable[[IO, IO], None],
    skip: bool,
    skippable: Tuple[Type[BaseException], ...],
    in_extensions: Set[str],
    out_extension: str,
) -> None:
    if out_path is None:
        raise RuntimeError("Positional OUT_PATH parameter shouldn't be empty")
    if not os.path.exists(out_path):
        os.mkdir(out_path)

    processed_files: set = set()
    for current_dir, _, files in os.walk(in_path):
        dir_prefix = os.path.commonpath([in_path, current_dir])
        relative_current_dir = os.path.relpath(current_dir, dir_prefix)
        current_out_path = os.path.normpath(
            os.path.join(out_path, relative_current_dir)
        )
        if not os.path.exists(current_out_path):
            os.mkdir(current_out_path)
        for file_name in files:
            _, ext = os.path.splitext(file_name)
            if ext not in in_extensions:
                continue

            in_file_path = os.path.join(current_dir, file_name)
            out_file_path = os.path.join(current_out_path, file_name)
            out_file_path = os.path.splitext(out_file_path)[0] + out_extension

            if in_file_path in processed_files or out_file_path in processed_files:
                continue

            processed_files.add(in_file_path)
            processed_files.add(out_file_path)

            with open(in_file_path, "r", encoding="utf-8") as in_file:
                print(in_file_path, file=sys.stderr, flush=True)
                try:
                    with open(out_file_path, "w", encoding="utf-8") as out_file:
                        convert_fn(in_file, out_file)
                except skippable:
                    if skip:
                        continue
                    raise


def _convert_stdin(convert_fn: Callable[[IO, IO], None]) -> None:
    convert_fn(sys.stdin, sys.stdout)
    sys.stdout.write("\n")
