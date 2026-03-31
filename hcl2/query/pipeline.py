"""Pipeline operator for chaining query stages."""

from dataclasses import dataclass
from typing import Any, List, Tuple

from hcl2.query.path import QuerySyntaxError, PathSegment, parse_path


@dataclass(frozen=True)
class PathStage:
    """A normal dotted-path stage."""

    segments: List[PathSegment]


@dataclass(frozen=True)
class BuiltinStage:
    """A builtin function stage (keys, values, length)."""

    name: str
    unpack: bool = False  # True when [*] suffix is used


@dataclass(frozen=True)
class SelectStage:
    """A select() predicate stage."""

    predicate: Any  # PredicateNode from predicate.py


@dataclass(frozen=True)
class ConstructStage:
    """A ``{field1, field2, key: .path}`` object construction stage."""

    fields: List[Tuple[str, List[PathSegment]]]  # [(output_key, path_segments), ...]


class _LocatedDict(dict):
    """Dict that carries source location metadata from a construct stage.

    When ``execute_pipeline`` builds a dict from a ``ConstructStage``, the
    input ``NodeView``'s ``_meta`` (line/column info) is stored here so
    downstream consumers (e.g. ``--with-location``) can still access it.
    """

    _source_meta: Any = None


def split_pipeline(query_str: str) -> List[str]:
    """Split a query string on ``|`` at depth 0.

    Tracks ``[]``, ``()`` depth and ``"..."`` quote state so that
    pipes inside brackets, parentheses, or strings are not split.

    Raises :class:`QuerySyntaxError` on empty stages.
    """
    stages: List[str] = []
    current: List[str] = []
    bracket_depth = 0
    paren_depth = 0
    brace_depth = 0
    in_string = False

    for i, char in enumerate(query_str):
        if in_string:
            current.append(char)
            if char == '"' and (i == 0 or query_str[i - 1] != "\\"):
                in_string = False
            continue

        if char == '"':
            in_string = True
            current.append(char)
        elif char == "[":
            bracket_depth += 1
            current.append(char)
        elif char == "]":
            bracket_depth -= 1
            current.append(char)
        elif char == "(":
            paren_depth += 1
            current.append(char)
        elif char == ")":
            paren_depth -= 1
            current.append(char)
        elif char == "{":
            brace_depth += 1
            current.append(char)
        elif char == "}":
            brace_depth -= 1
            current.append(char)
        elif (
            char == "|" and bracket_depth == 0 and paren_depth == 0 and brace_depth == 0
        ):
            stage = "".join(current).strip()
            if not stage:
                raise QuerySyntaxError("Empty stage in pipeline")
            stages.append(stage)
            current = []
        else:
            current.append(char)

    # Final stage
    tail = "".join(current).strip()
    if not tail and stages:
        raise QuerySyntaxError("Empty stage in pipeline")
    if tail:
        stages.append(tail)

    if not stages:
        raise QuerySyntaxError("Empty pipeline")

    return stages


def classify_stage(stage_str: str) -> Any:
    """Classify a stage string into a PipeStage type.

    - ``select(...)`` → :class:`SelectStage`
    - ``keys`` / ``values`` / ``length`` → :class:`BuiltinStage`
    - Otherwise → :class:`PathStage`
    """
    from hcl2.query.builtins import BUILTIN_NAMES

    stripped = stage_str.strip()

    # Strip trailing ? (optional operator is a no-op at stage level)
    if stripped.endswith("?"):
        stripped = stripped[:-1].rstrip()

    if stripped.startswith("select(") and stripped.endswith(")"):
        from hcl2.query.predicate import parse_predicate

        inner = stripped[len("select(") : -1]
        predicate = parse_predicate(inner)
        return SelectStage(predicate=predicate)

    if stripped in BUILTIN_NAMES:
        return BuiltinStage(name=stripped)

    # Allow builtin[*] to unpack list results into individual items
    if stripped.endswith("[*]") and stripped[:-3] in BUILTIN_NAMES:
        return BuiltinStage(name=stripped[:-3], unpack=True)

    # Object construction: {field1, field2} or {key: .path, ...}
    if stripped.startswith("{") and stripped.endswith("}"):
        fields = _parse_construct(stripped[1:-1])
        return ConstructStage(fields=fields)

    # Allow jq-style leading dot (e.g. ".foo" in a pipe stage)
    path_str = stripped
    if path_str.startswith(".") and len(path_str) > 1 and path_str[1] != ".":
        path_str = path_str[1:]

    return PathStage(segments=parse_path(path_str))


def _split_construct_fields(inner: str) -> List[str]:
    """Split the inner part of ``{...}`` on commas, respecting brackets and parens."""
    fields: List[str] = []
    current: List[str] = []
    bracket_depth = 0
    paren_depth = 0

    for char in inner:
        if char == "[":
            bracket_depth += 1
            current.append(char)
        elif char == "]":
            bracket_depth -= 1
            current.append(char)
        elif char == "(":
            paren_depth += 1
            current.append(char)
        elif char == ")":
            paren_depth -= 1
            current.append(char)
        elif char == "," and bracket_depth == 0 and paren_depth == 0:
            field = "".join(current).strip()
            if field:
                fields.append(field)
            current = []
        else:
            current.append(char)

    tail = "".join(current).strip()
    if tail:
        fields.append(tail)

    return fields


def _parse_construct(inner: str) -> List[Tuple[str, List[PathSegment]]]:
    """Parse the fields inside ``{...}`` into (key, path_segments) pairs."""
    raw_fields = _split_construct_fields(inner)
    if not raw_fields:
        raise QuerySyntaxError("Empty object construction: {}")

    result: List[Tuple[str, List[PathSegment]]] = []
    for field in raw_fields:
        if ":" in field:
            # Renamed: key: .path
            colon_idx = field.index(":")
            key = field[:colon_idx].strip()
            path_str = field[colon_idx + 1 :].strip()
            if path_str.startswith(".") and len(path_str) > 1:
                path_str = path_str[1:]
            result.append((key, parse_path(path_str)))
        elif field.startswith("."):
            # Dotted shorthand: .path → key=last segment
            path_str = field[1:]
            segments = parse_path(path_str)
            key = segments[-1].name
            result.append((key, segments))
        else:
            # Shorthand: field_name → key=field_name, path=field_name
            result.append((field, parse_path(field)))

    return result


def _unwrap_construct_value(value: Any) -> Any:
    """Unwrap an AttributeView to its value for object construction.

    When constructing ``{name, type}``, resolving ``name`` returns an
    ``AttributeView`` whose ``to_dict()`` produces ``{"name": "..."}``
    — but we want just the value, not the key-value wrapper.
    """
    from hcl2.query.attributes import AttributeView

    if isinstance(value, AttributeView):
        return value.value_node
    if isinstance(value, list):
        return [_unwrap_construct_value(v) for v in value]
    return value


def _to_json_value(value: Any) -> Any:
    """Convert a value to a JSON-serializable Python value."""
    from hcl2.query._base import NodeView

    if isinstance(value, NodeView):
        return value.to_dict()
    if isinstance(value, list):
        return [_to_json_value(v) for v in value]
    return value


def _resolve_path_item(item: Any, segments: List[PathSegment]) -> List[Any]:
    """Resolve a path stage against a single item.

    Tries property access, then structural resolution, then structural
    resolution on an unwrapped version of the item.  As a last resort,
    checks whether the unwrapped item itself satisfies a type-qualifier
    filter (so ``object:*`` in a pipe stage acts like ``select(.type == …)``).
    """
    from hcl2.query._base import NodeView
    from hcl2.query.resolver import resolve_path

    if not isinstance(item, NodeView):
        return []

    # Try property access first (before unwrapping)
    prop = _try_property_access(item, segments)
    if prop is not None:
        return [prop]

    # Structural resolution on the item as-is
    resolved = resolve_path(item, segments)
    if resolved:
        return resolved

    # Try structural resolution on unwrapped item
    unwrapped_item = _unwrap_single(item)
    if unwrapped_item is not item:
        resolved = resolve_path(unwrapped_item, segments)
        if resolved:
            return resolved

    # Last resort: single type-qualified wildcard in a pipe stage can match
    # the unwrapped item itself (e.g. ``| object:*`` keeps only objects).
    if unwrapped_item is not item:
        matched = _try_type_match(unwrapped_item, segments)
        if matched is not None:
            return [matched]

    return []


# pylint: disable-next=too-many-locals
def execute_pipeline(root: Any, stages: List[Any], file_path: str = "") -> List[Any]:
    """Execute a list of stages against a root view.

    Starts with ``[root]`` and feeds results through each stage.
    """
    from hcl2.query.builtins import apply_builtin
    from hcl2.query.predicate import evaluate_predicate

    results: List[Any] = [root]

    for i, stage in enumerate(stages):
        next_results: List[Any] = []

        if isinstance(stage, PathStage):
            for item in results:
                next_results.extend(_resolve_path_item(item, stage.segments))

            # When the next stage is a builtin or select, unwrap so they
            # see underlying values instead of wrapper views.
            # Don't unwrap for ConstructStage — it needs original views
            # for property access like .block_type, .name_labels.
            if i < len(stages) - 1 and not isinstance(
                stages[i + 1], (PathStage, ConstructStage)
            ):
                next_results = _unwrap_for_next_stage(next_results)

        elif isinstance(stage, BuiltinStage):
            next_results = apply_builtin(stage.name, results)
            if stage.unpack:
                unpacked: List[Any] = []
                for item in next_results:
                    if isinstance(item, list):
                        unpacked.extend(item)
                    else:
                        unpacked.append(item)
                next_results = unpacked
        elif isinstance(stage, SelectStage):
            for item in results:
                if evaluate_predicate(stage.predicate, item):
                    next_results.append(item)
        elif isinstance(stage, ConstructStage):
            from hcl2.query._base import NodeView

            for item in results:
                obj = _LocatedDict()
                if isinstance(item, NodeView):
                    obj._source_meta = getattr(item.raw, "_meta", None)
                elif isinstance(item, _LocatedDict):
                    obj._source_meta = item._source_meta
                for key, segments in stage.fields:
                    # __file__ is a virtual field resolved to the source path
                    if len(segments) == 1 and segments[0].name == "__file__":
                        obj[key] = file_path
                        continue
                    resolved = _resolve_path_item(item, segments)
                    if resolved:
                        val = resolved[0] if len(resolved) == 1 else resolved
                        obj[key] = _to_json_value(_unwrap_construct_value(val))
                    else:
                        obj[key] = None
                next_results.append(obj)
        else:
            raise QuerySyntaxError(f"Unknown stage type: {stage!r}")

        results = next_results
        if not results:
            return []

    return results


def _try_type_match(node: Any, segments: List[PathSegment]) -> Any:
    """Check if a node matches a single type-qualified wildcard segment.

    Enables ``| object:*`` as a pipe-stage type filter.  Returns the node
    if it matches, or ``None`` otherwise.
    """
    from hcl2.query._base import NodeView, view_type_name

    if len(segments) != 1:
        return None

    seg = segments[0]
    if seg.type_filter is None or seg.name != "*":
        return None

    if not isinstance(node, NodeView):
        return None

    if view_type_name(node) == seg.type_filter:
        return node
    return None


def _try_property_access(  # pylint: disable=too-many-return-statements
    node: Any, segments: List[PathSegment]
) -> Any:
    """Try resolving segments as Python property accesses on a view.

    Falls back to this when structural resolution returns nothing.
    Only handles single-segment paths (no dots) with no type filter.
    Returns the property value, or ``None`` if no matching property exists.
    """
    from hcl2.query._base import NodeView

    if len(segments) != 1:
        return None

    seg = segments[0]
    if seg.type_filter is not None or not isinstance(node, NodeView):
        return None

    # Check for a Python property on the view class
    # In query context, .value resolves to .value_node so it formats
    # consistently across output modes (HCL expression, not ${...} wrapped).
    prop_name = seg.name
    if prop_name == "value" and hasattr(type(node), "value_node"):
        prop_name = "value_node"

    prop_descriptor = getattr(type(node), prop_name, None)
    if not isinstance(prop_descriptor, property):
        return None

    value = getattr(node, prop_name)

    # Apply index/select_all to list-valued properties
    if seg.select_all and isinstance(value, list):
        return value
    if seg.index is not None and isinstance(value, list):
        if 0 <= seg.index < len(value):
            return value[seg.index]
        return None

    return value


def _unwrap_single(item: Any) -> Any:
    """Unwrap a single view for structural resolution.

    Returns the unwrapped view, or the original item if no unwrapping applies.
    """
    from hcl2.query._base import NodeView, view_for
    from hcl2.query.attributes import AttributeView
    from hcl2.query.blocks import BlockView
    from hcl2.rules.expressions import ExprTermRule

    if isinstance(item, AttributeView):
        item = item.value_node
    elif isinstance(item, BlockView):
        item = item.body
    if isinstance(item, NodeView) and isinstance(item._node, ExprTermRule):
        inner = item._node.expression
        if inner is not None:
            item = view_for(inner)
    return item


def _unwrap_for_next_stage(results: List[Any]) -> List[Any]:
    """Unwrap views for pipeline chaining between stages.

    - AttributeView → value node (unwrapped from ExprTermRule)
    - BlockView → body (so subsequent stages see attributes/blocks, not labels)
    - ExprTermRule wrapper → concrete inner view
    """
    from hcl2.query._base import NodeView, view_for
    from hcl2.query.attributes import AttributeView
    from hcl2.query.blocks import BlockView
    from hcl2.rules.expressions import ExprTermRule

    unwrapped: List[Any] = []
    for item in results:
        if isinstance(item, AttributeView):
            item = item.value_node
        elif isinstance(item, BlockView):
            item = item.body
        # Unwrap ExprTermRule wrappers to concrete view types
        if isinstance(item, NodeView) and isinstance(item._node, ExprTermRule):
            inner = item._node.expression
            if inner is not None:
                item = view_for(inner)
        unwrapped.append(item)
    return unwrapped
