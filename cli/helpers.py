"""Shared file-conversion helpers for the HCL2 CLI commands."""

import glob as glob_mod
import json
import os
import signal
import sys
from io import StringIO
from typing import Callable, IO, List, Optional, Set, Tuple, Type

from lark import UnexpectedCharacters, UnexpectedToken

# Exit codes shared across CLIs
EXIT_SUCCESS = 0
EXIT_PARTIAL = 1  # hcl2tojson: some files skipped; jsontohcl2: JSON/encoding error
EXIT_PARSE_ERROR = 2  # hcl2tojson: all unparsable; jsontohcl2: bad HCL structure
EXIT_IO_ERROR = 4
EXIT_DIFF = 5  # jsontohcl2 --diff: differences found

# Exceptions that can be skipped when -s is passed
HCL_SKIPPABLE = (UnexpectedToken, UnexpectedCharacters, UnicodeDecodeError)
JSON_SKIPPABLE = (json.JSONDecodeError, UnicodeDecodeError)


def _install_sigpipe_handler() -> None:
    """Reset SIGPIPE to default so piping to ``head`` etc. exits cleanly."""
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def _error(msg: str, use_json: bool = False, **extra) -> str:
    """Format an error message for stderr.

    When *use_json* is true the result is a single-line JSON object with
    ``error`` and ``message`` keys (plus any *extra* fields).  Otherwise
    a plain ``Error: …`` string is returned.
    """
    if use_json:
        data: dict = {"error": extra.pop("error_type", "error"), "message": msg}
        data.update(extra)
        return json.dumps(data)
    return f"Error: {msg}"


def _expand_file_args(file_args: List[str]) -> List[str]:
    """Expand glob patterns in file arguments.

    For each arg containing glob metacharacters (``*``, ``?``, ``[``),
    expand via :func:`glob.glob` with ``recursive=True``.  Literal paths
    and ``-`` (stdin) pass through unchanged.  If a glob matches nothing,
    the literal pattern is kept so the caller produces an IO error.
    """
    expanded: List[str] = []
    for arg in file_args:
        if arg == "-":
            expanded.append(arg)
            continue
        if any(c in arg for c in "*?["):
            matches = sorted(glob_mod.glob(arg, recursive=True))
            if matches:
                expanded.extend(matches)
            else:
                expanded.append(arg)  # keep literal — will produce IO error
        else:
            expanded.append(arg)
    return expanded


def _collect_files(path: str, extensions: Set[str]) -> List[str]:
    """Return a sorted list of files under *path* matching *extensions*.

    If *path* is ``-`` (stdin marker) or a plain file, it is returned as-is
    in a single-element list.  Directories are walked recursively.
    """
    if path == "-":
        return ["-"]
    if os.path.isfile(path):
        return [path]
    if os.path.isdir(path):
        files: List[str] = []
        for dirpath, _, filenames in os.walk(path):
            for fname in filenames:
                if os.path.splitext(fname)[1] in extensions:
                    files.append(os.path.join(dirpath, fname))
        files.sort()
        return files
    # Not a file or directory — return as-is so caller can report IO error
    return [path]


def _convert_single_file(  # pylint: disable=too-many-positional-arguments
    in_path: str,
    out_path: Optional[str],
    convert_fn: Callable[[IO, IO], None],
    skip: bool,
    skippable: Tuple[Type[BaseException], ...],
    quiet: bool = False,
) -> bool:
    """Convert a single file.  Returns ``True`` on success, ``False`` if skipped."""
    if in_path == "-":
        if out_path is not None:
            try:
                with open(out_path, "w", encoding="utf-8") as out_file:
                    convert_fn(sys.stdin, out_file)
            except skippable:
                if skip:
                    if os.path.exists(out_path):
                        os.remove(out_path)
                    return False
                raise
            return True
        return _convert_single_stream(sys.stdin, convert_fn, skip, skippable)
    with open(in_path, "r", encoding="utf-8") as in_file:
        if not quiet:
            print(in_path, file=sys.stderr, flush=True)
        if out_path is not None:
            try:
                with open(out_path, "w", encoding="utf-8") as out_file:
                    convert_fn(in_file, out_file)
            except skippable:
                if skip:
                    if os.path.exists(out_path):
                        os.remove(out_path)
                    return False
                raise
        elif skip:
            buf = StringIO()
            try:
                convert_fn(in_file, buf)
            except skippable:
                return False
            sys.stdout.write(buf.getvalue())
            sys.stdout.write("\n")
        else:
            convert_fn(in_file, sys.stdout)
            sys.stdout.write("\n")
    return True


def _convert_directory(  # pylint: disable=too-many-positional-arguments,too-many-locals
    in_path: str,
    out_path: Optional[str],
    convert_fn: Callable[[IO, IO], None],
    skip: bool,
    skippable: Tuple[Type[BaseException], ...],
    in_extensions: Set[str],
    out_extension: str,
    quiet: bool = False,
) -> bool:
    """Convert all matching files in a directory.  Returns ``True`` if any were skipped."""
    if out_path is None:
        raise RuntimeError("Output path is required for directory conversion (use -o)")
    if not os.path.exists(out_path):
        os.makedirs(out_path)

    any_skipped = False
    processed_files: set = set()
    for current_dir, _, files in os.walk(in_path):
        dir_prefix = os.path.commonpath([in_path, current_dir])
        relative_current_dir = os.path.relpath(current_dir, dir_prefix)
        current_out_path = os.path.normpath(
            os.path.join(out_path, relative_current_dir)
        )
        if not os.path.exists(current_out_path):
            os.makedirs(current_out_path)
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
                if not quiet:
                    print(in_file_path, file=sys.stderr, flush=True)
                try:
                    with open(out_file_path, "w", encoding="utf-8") as out_file:
                        convert_fn(in_file, out_file)
                except skippable:
                    if skip:
                        any_skipped = True
                        if os.path.exists(out_file_path):
                            os.remove(out_file_path)
                        continue
                    raise
    return any_skipped


def _convert_multiple_files(  # pylint: disable=too-many-positional-arguments
    in_paths: List[str],
    out_path: str,
    convert_fn: Callable[[IO, IO], None],
    skip: bool,
    skippable: Tuple[Type[BaseException], ...],
    out_extension: str,
    quiet: bool = False,
) -> bool:
    """Convert multiple files into an output directory.

    Preserves relative path structure to avoid basename collisions when
    files from different directories share the same name.  Returns ``True``
    if any files were skipped.
    """
    if not os.path.exists(out_path):
        os.makedirs(out_path)
    abs_paths = [os.path.abspath(p) for p in in_paths]
    common = os.path.commonpath(abs_paths) if len(abs_paths) > 1 else ""
    if common and not os.path.isdir(common):
        common = os.path.dirname(common)
    any_skipped = False
    for in_path, abs_path in zip(in_paths, abs_paths):
        if common:
            rel = os.path.relpath(abs_path, common)
        else:
            rel = os.path.basename(in_path)
        dest = os.path.splitext(rel)[0] + out_extension
        file_out = os.path.join(out_path, dest)
        file_out_dir = os.path.dirname(file_out)
        if file_out_dir and not os.path.exists(file_out_dir):
            os.makedirs(file_out_dir)
        if not _convert_single_file(
            in_path, file_out, convert_fn, skip, skippable, quiet=quiet
        ):
            any_skipped = True
    return any_skipped


def _convert_single_stream(
    in_file: IO,
    convert_fn: Callable[[IO, IO], None],
    skip: bool,
    skippable: Tuple[Type[BaseException], ...],
) -> bool:
    """Convert from a stream (e.g. stdin) to stdout.  Returns ``True`` on success."""
    if skip:
        buf = StringIO()
        try:
            convert_fn(in_file, buf)
        except skippable:
            return False
        sys.stdout.write(buf.getvalue())
        sys.stdout.write("\n")
    else:
        convert_fn(in_file, sys.stdout)
        sys.stdout.write("\n")
    return True
