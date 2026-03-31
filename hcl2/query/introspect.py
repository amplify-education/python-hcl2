"""Introspection utilities for --describe and --schema flags."""

import inspect
from typing import Any, Dict, List

from hcl2.query._base import NodeView, _VIEW_REGISTRY
from hcl2.query.safe_eval import _SAFE_CALLABLE_NAMES


def describe_results(results: List[Any]) -> Dict[str, Any]:
    """Build a description dict for --describe output."""
    described = []
    for result in results:
        if isinstance(result, NodeView):
            described.append(_describe_view(result))
        else:
            described.append(
                {
                    "type": type(result).__name__,
                    "value": repr(result),
                }
            )
    return {"results": described}


def _describe_view(view: NodeView) -> Dict[str, Any]:
    """Describe a single view instance."""
    cls = type(view)
    props = []
    methods = []

    for name, obj in inspect.getmembers(cls):
        if name.startswith("_"):
            continue
        if isinstance(obj, property):
            props.append(name)
        elif callable(obj) and not isinstance(obj, (staticmethod, classmethod)):
            sig = ""
            try:
                sig = str(inspect.signature(obj))
            except (ValueError, TypeError):
                pass
            methods.append(f"{name}{sig}")

    summary = _summarize_view(view)

    result: Dict[str, Any] = {
        "type": cls.__name__,
        "properties": props,
        "methods": methods,
    }
    if summary:
        result["summary"] = summary
    return result


def _summarize_view(view: NodeView) -> str:
    """Generate a brief summary string for a view."""
    from hcl2.query.blocks import BlockView
    from hcl2.query.attributes import AttributeView

    if isinstance(view, BlockView):
        return f"block_type={view.block_type!r}, labels={view.labels!r}"
    if isinstance(view, AttributeView):
        return f"name={view.name!r}"
    return ""


def build_schema() -> Dict[str, Any]:
    """Build the full view API schema for --schema output."""
    views = {}
    for rule_type, view_cls in _VIEW_REGISTRY.items():
        views[view_cls.__name__] = _schema_for_class(view_cls, rule_type)

    # Add base NodeView
    views["NodeView"] = _schema_for_class(NodeView, None)

    return {
        "docs": "https://github.com/amplify-education/python-hcl2/tree/main/docs",
        "query_guide": {
            "mode_preference": [
                "1. Structural (default) — preferred for all queries. jq-like syntax.",
                "2. Hybrid (::) — only when you need Python on structural results.",
                "3. Eval (-e) — last resort. Many expressions are blocked for safety.",
            ],
            "structural_syntax": {
                "navigate": "resource.aws_instance.main.ami",
                "wildcard": "variable[*]",
                "skip_labels": "resource~[*]",
                "pipes": "resource[*] | .tags | keys",
                "select": "resource~[select(.ami)]",
                "string_functions": (
                    'select(.source | contains("x")), '
                    'select(.ami | test("^ami-")), '
                    'select(.name | startswith("prod-")), '
                    'select(.path | endswith("/api"))'
                ),
                "has": 'select(has("tags"))',
                "postfix_not": "select(.tags | not)",
                "any_all": 'any(.elements; .type == "function_call")',
                "construct": "{name: .name, type: .block_type, file: .__file__}",
                "recursive": "*..function_call:*",
                "optional": "nonexistent?",
            },
            "output_flags": {
                "--json": "JSON output",
                "--value": "Raw value (keeps quotes on strings)",
                "--raw": "Raw value (strips quotes, ideal for shell piping)",
                "--no-filename": "Suppress filename prefix in multi-file mode",
            },
            "examples": [
                "hq 'resource.aws_instance~[*] | .ami' dir/ --raw",
                "hq 'module~[select(.source | contains(\"docker\"))]' dir/ --json",
                "hq 'resource~[select(has(\"tags\"))] | {name: .name_labels, tags}' dir/ --json",
                "hq 'variable~[select(.default)] | {name: .name_labels, default}' . --raw",
                "hq file1.tf --diff file2.tf --json",
            ],
        },
        "views": views,
        "eval_namespace": {
            "note": "Eval mode (-e) is a last resort. Prefer structural queries.",
            "builtins": sorted(_SAFE_CALLABLE_NAMES),
            "variables": {
                "doc": "DocumentView",
                "_": "NodeView (per-result in hybrid mode)",
            },
        },
    }


# pylint: disable-next=too-many-locals
def _schema_for_class(cls, rule_type) -> Dict[str, Any]:
    """Build schema for a single view class."""
    result: Dict[str, Any] = {}
    if rule_type is not None:
        result["wraps"] = rule_type.__name__

    props = {}
    methods = {}
    static_methods = {}

    # Collect staticmethod names from __dict__ of cls and its bases
    static_names = set()
    for klass in cls.__mro__:
        for attr_name, attr_val in klass.__dict__.items():
            if isinstance(attr_val, staticmethod):
                static_names.add(attr_name)

    for name in sorted(dir(cls)):
        if name.startswith("_"):
            continue
        obj = getattr(cls, name)
        if isinstance(obj, property):
            # Get return annotation if available
            ann = ""
            if obj.fget and hasattr(obj.fget, "__annotations__"):
                ret = obj.fget.__annotations__.get("return")
                if ret:
                    ann = str(ret)
            prop_info: Dict[str, str] = {"type": ann or "Any"}
            # Extract description from property docstring
            doc = obj.fget.__doc__ if obj.fget else None
            if doc:
                prop_info["description"] = doc.strip()
            props[name] = prop_info
        elif name in static_names:
            try:
                sig = str(inspect.signature(obj))
            except (ValueError, TypeError):
                sig = "(...)"
            static_methods[name] = sig
        elif callable(obj):
            try:
                sig = str(inspect.signature(obj))
            except (ValueError, TypeError):
                sig = "(...)"
            methods[name] = sig

    if props:
        result["properties"] = props
    if methods:
        result["methods"] = methods
    if static_methods:
        result["static_methods"] = static_methods

    return result
