"""Structural path parser for the hq query language."""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


class QuerySyntaxError(Exception):
    """Raised when a structural path cannot be parsed."""


@dataclass(frozen=True)
class PathSegment:
    """A single segment in a structural path."""

    name: str  # identifier or "*" for wildcard
    select_all: bool  # True if [*] suffix
    index: Optional[int]  # integer if [N] suffix, None otherwise
    recursive: bool = False  # True for ".." recursive descent
    predicate: object = None  # PredicateNode if [select(...)] suffix
    type_filter: Optional[str] = None  # e.g. "function_call" in function_call:name
    skip_labels: bool = False  # True if ~ suffix (skip remaining block labels)


# Optional type qualifier prefix:  type_filter:name~?[bracket]?
_SEGMENT_RE = re.compile(
    r"^(?:([a-z_]+):)?([a-zA-Z_][a-zA-Z0-9_-]*|\*)(~)?(?:\[(\*|[0-9]+)\])?\??$"
)


def parse_path(path_str: str) -> List[PathSegment]:  # pylint: disable=too-many-locals
    """Parse a structural path string into segments.

    Grammar:
        path    := segment ("." segment)*
        segment := name ("[*]" | "[" INT "]")?
        name    := "*" | IDENTIFIER

    Raises QuerySyntaxError on invalid input.
    """
    if not path_str or not path_str.strip():
        raise QuerySyntaxError("Empty path")

    # jq compat: .[] is an alias for [*]
    path_str = path_str.replace(".[]", "[*]")

    segments: List[PathSegment] = []
    parts = _split_path(path_str)

    for is_recursive, part in parts:
        # Check for [select(...)] syntax
        select_match = _extract_select(part)
        if select_match is not None:
            seg_name, predicate, type_filter, skip, sel_all, sel_idx = select_match
            segments.append(
                PathSegment(
                    name=seg_name,
                    select_all=sel_all,
                    index=sel_idx,
                    recursive=is_recursive,
                    predicate=predicate,
                    type_filter=type_filter,
                    skip_labels=skip,
                )
            )
            continue

        match = _SEGMENT_RE.match(part)
        if not match:
            raise QuerySyntaxError(f"Invalid path segment: {part!r} in {path_str!r}")

        type_filter = match.group(1)  # optional "type:" prefix
        name = match.group(2)
        skip_labels = match.group(3) is not None  # "~" suffix
        bracket = match.group(4)

        if bracket is None:
            segments.append(
                PathSegment(
                    name=name,
                    select_all=False,
                    index=None,
                    recursive=is_recursive,
                    type_filter=type_filter,
                    skip_labels=skip_labels,
                )
            )
        elif bracket == "*":
            segments.append(
                PathSegment(
                    name=name,
                    select_all=True,
                    index=None,
                    recursive=is_recursive,
                    type_filter=type_filter,
                    skip_labels=skip_labels,
                )
            )
        else:
            segments.append(
                PathSegment(
                    name=name,
                    select_all=False,
                    index=int(bracket),
                    recursive=is_recursive,
                    type_filter=type_filter,
                    skip_labels=skip_labels,
                )
            )

    return segments


# pylint: disable-next=too-many-statements
def _split_path(path_str: str) -> List[Tuple[bool, str]]:
    """Split a path string into (is_recursive, segment_text) pairs.

    Handles both single dots (normal) and double dots (recursive descent).
    Bracket-aware: dots inside ``[...]`` are not treated as separators.
    """
    result: List[Tuple[bool, str]] = []
    i = 0
    current: List[str] = []
    bracket_depth = 0
    paren_depth = 0

    while i < len(path_str):
        char = path_str[i]

        if char == "[":
            bracket_depth += 1
            current.append(char)
            i += 1
        elif char == "]":
            bracket_depth -= 1
            current.append(char)
            i += 1
        elif char == "(":
            paren_depth += 1
            current.append(char)
            i += 1
        elif char == ")":
            paren_depth -= 1
            current.append(char)
            i += 1
        elif char == '"':
            # Consume entire quoted string, respecting escaped quotes
            current.append(char)
            i += 1
            while i < len(path_str) and path_str[i] != '"':
                if path_str[i] == "\\" and i + 1 < len(path_str):
                    current.append(path_str[i])
                    i += 1
                current.append(path_str[i])
                i += 1
            if i < len(path_str):
                current.append(path_str[i])
                i += 1
        elif char == "." and bracket_depth == 0 and paren_depth == 0:
            # Emit current segment if any
            if current:
                result.append((False, "".join(current)))
                current = []
            elif not result:
                raise QuerySyntaxError(f"Path cannot start with '.': {path_str!r}")

            # Check for ".." (recursive descent)
            if i + 1 < len(path_str) and path_str[i + 1] == ".":
                i += 2  # skip both dots
                # Collect the next segment (respecting brackets)
                next_seg: List[str] = []
                bracket_depth = 0
                while i < len(path_str):
                    char = path_str[i]
                    if char == "[":
                        bracket_depth += 1
                    elif char == "]":
                        bracket_depth -= 1
                    elif char == "." and bracket_depth == 0:
                        break
                    next_seg.append(char)
                    i += 1
                if not next_seg:
                    raise QuerySyntaxError(f"Expected segment after '..': {path_str!r}")
                result.append((True, "".join(next_seg)))
            else:
                i += 1  # skip single dot
        else:
            current.append(char)
            i += 1

    if current:
        result.append((False, "".join(current)))

    if not result:
        raise QuerySyntaxError(f"Empty path: {path_str!r}")

    return result


def _extract_select(part: str) -> Optional[tuple]:  # pylint: disable=too-many-locals
    """Extract ``name[select(...)]`` from a segment string.

    Returns ``(name, predicate_node)`` or ``None`` if not a select bracket.
    """
    select_marker = "[select("
    idx = part.find(select_marker)
    if idx == -1:
        return None

    seg_name = part[:idx]
    if not seg_name or not re.match(
        r"^(?:[a-z_]+:)?(?:[a-zA-Z_][a-zA-Z0-9_-]*|\*)~?$", seg_name
    ):
        raise QuerySyntaxError(f"Invalid segment name before [select(): {seg_name!r}")

    # Parse optional type_filter:name prefix
    type_filter = None
    if ":" in seg_name:
        type_filter, seg_name = seg_name.split(":", 1)

    # Parse optional ~ suffix
    skip_labels = seg_name.endswith("~")
    if skip_labels:
        seg_name = seg_name[:-1]

    # Find matching )] for select(...), allowing optional trailing [*] or [N]
    inner_start = idx + len(select_marker)
    close_idx = part.find(")]", inner_start)
    if close_idx == -1:
        raise QuerySyntaxError(f"Expected )] at end of select bracket in: {part!r}")
    inner = part[inner_start:close_idx]
    tail = part[close_idx + 2 :]  # text after ")]"

    from hcl2.query.predicate import parse_predicate

    predicate = parse_predicate(inner)

    # Parse optional trailing [*] or [N] after [select(...)], with optional ?
    select_all = True  # default: select returns all matches
    index = None
    if tail:
        # Strip trailing ? (optional operator is a no-op at segment level)
        clean_tail = tail.rstrip("?")
        if clean_tail:
            tail_match = re.match(r"^\[(\*|[0-9]+)\]$", clean_tail)
            if not tail_match:
                raise QuerySyntaxError(
                    f"Unexpected suffix after [select(...)]: {tail!r} in {part!r}"
                )
            bracket = tail_match.group(1)
            if bracket == "*":
                select_all = True
            else:
                select_all = False
                index = int(bracket)

    return (seg_name, predicate, type_filter, skip_labels, select_all, index)
