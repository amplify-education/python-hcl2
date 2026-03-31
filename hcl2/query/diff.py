"""Structural diff between two HCL documents."""

import json
from dataclasses import dataclass
from typing import Any, List


@dataclass
class DiffEntry:
    """A single difference between two structures."""

    path: str
    kind: str  # "added", "removed", "changed"
    left: Any = None
    right: Any = None


def diff_dicts(left: Any, right: Any, path: str = "") -> List[DiffEntry]:
    """Recursively compare two Python structures and return differences."""
    entries: List[DiffEntry] = []

    if isinstance(left, dict) and isinstance(right, dict):
        all_keys = sorted(set(list(left.keys()) + list(right.keys())))
        for key in all_keys:
            child_path = f"{path}.{key}" if path else key
            if key not in left:
                entries.append(
                    DiffEntry(path=child_path, kind="added", right=right[key])
                )
            elif key not in right:
                entries.append(
                    DiffEntry(path=child_path, kind="removed", left=left[key])
                )
            else:
                entries.extend(diff_dicts(left[key], right[key], child_path))
    elif isinstance(left, list) and isinstance(right, list):
        max_len = max(len(left), len(right))
        for i in range(max_len):
            child_path = f"{path}[{i}]"
            if i >= len(left):
                entries.append(DiffEntry(path=child_path, kind="added", right=right[i]))
            elif i >= len(right):
                entries.append(DiffEntry(path=child_path, kind="removed", left=left[i]))
            else:
                entries.extend(diff_dicts(left[i], right[i], child_path))
    elif left != right:
        entries.append(
            DiffEntry(path=path or "(root)", kind="changed", left=left, right=right)
        )

    return entries


def format_diff_text(entries: List[DiffEntry]) -> str:
    """Format diff entries as human-readable text."""
    if not entries:
        return ""
    lines: List[str] = []
    for entry in entries:
        if entry.kind == "added":
            lines.append(f"+ {entry.path}: {_fmt_val(entry.right)}")
        elif entry.kind == "removed":
            lines.append(f"- {entry.path}: {_fmt_val(entry.left)}")
        elif entry.kind == "changed":
            lines.append(
                f"~ {entry.path}: {_fmt_val(entry.left)} -> {_fmt_val(entry.right)}"
            )
    return "\n".join(lines)


def format_diff_json(entries: List[DiffEntry]) -> str:
    """Format diff entries as JSON."""
    data = []
    for entry in entries:
        item: dict = {"path": entry.path, "kind": entry.kind}
        if entry.left is not None:
            item["left"] = entry.left
        if entry.right is not None:
            item["right"] = entry.right
        data.append(item)
    return json.dumps(data, indent=2, default=str)


def _fmt_val(val: Any) -> str:
    """Format a value for text diff display."""
    if isinstance(val, str):
        return repr(val)
    return str(val)
