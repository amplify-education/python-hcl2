"""Built-in terminal transforms for the hq query pipeline."""

from typing import Any, List

from hcl2.query.path import QuerySyntaxError

BUILTIN_NAMES = frozenset({"keys", "values", "length"})


def apply_builtin(name: str, nodes: List[Any]) -> List[Any]:
    """Apply a builtin function to a list of nodes.

    Each builtin produces one result per input node.
    """
    nodes = _unwrap_to_values(nodes)
    if name == "keys":
        return _apply_keys(nodes)
    if name == "values":
        return _apply_values(nodes)
    if name == "length":
        return _apply_length(nodes)
    raise QuerySyntaxError(f"Unknown builtin: {name!r}")


def _unwrap_to_values(nodes: List[Any]) -> List[Any]:
    """Unwrap AttributeView and ExprTermRule wrappers for builtins."""
    from hcl2.query._base import NodeView, view_for
    from hcl2.query.attributes import AttributeView
    from hcl2.rules.expressions import ExprTermRule

    result: List[Any] = []
    for node in nodes:
        if isinstance(node, AttributeView):
            node = node.value_node
        if isinstance(node, NodeView) and isinstance(node._node, ExprTermRule):
            inner = node._node.expression
            if inner is not None:
                node = view_for(inner)
        result.append(node)
    return result


def _apply_keys(nodes: List[Any]) -> List[Any]:
    from hcl2.query.blocks import BlockView
    from hcl2.query.body import BodyView, DocumentView
    from hcl2.query.containers import ObjectView

    results: List[Any] = []
    for node in nodes:
        if isinstance(node, ObjectView):
            results.append(node.keys)
        elif isinstance(node, (DocumentView, BodyView)):
            body = node.body if isinstance(node, DocumentView) else node
            names: List[str] = []
            for blk in body.blocks():
                names.append(blk.block_type)  # type: ignore[attr-defined]
            for attr in body.attributes():
                names.append(attr.name)  # type: ignore[attr-defined]
            results.append(names)
        elif isinstance(node, BlockView):
            results.append(node.labels)
        elif isinstance(node, dict):
            results.append(list(node.keys()))
        # other types silently produce nothing
    return results


def _apply_values(nodes: List[Any]) -> List[Any]:
    from hcl2.query.body import BodyView, DocumentView
    from hcl2.query.containers import ObjectView, TupleView

    results: List[Any] = []
    for node in nodes:
        if isinstance(node, ObjectView):
            results.append([v for _, v in node.entries])
        elif isinstance(node, TupleView):
            results.append(node.elements)
        elif isinstance(node, (DocumentView, BodyView)):
            body = node.body if isinstance(node, DocumentView) else node
            items: list = []
            items.extend(body.blocks())
            items.extend(body.attributes())
            results.append(items)
        elif isinstance(node, dict):
            results.append(list(node.values()))
        elif isinstance(node, list):
            results.append(node)
    return results


def _apply_length(nodes: List[Any]) -> List[Any]:
    from hcl2.query._base import NodeView
    from hcl2.query.body import BodyView, DocumentView
    from hcl2.query.containers import ObjectView, TupleView
    from hcl2.query.functions import FunctionCallView

    results: List[Any] = []
    for node in nodes:
        if isinstance(node, TupleView):
            results.append(len(node))
        elif isinstance(node, ObjectView):
            results.append(len(node.entries))
        elif isinstance(node, FunctionCallView):
            results.append(len(node.args))
        elif isinstance(node, (DocumentView, BodyView)):
            body = node.body if isinstance(node, DocumentView) else node
            results.append(len(body.blocks()) + len(body.attributes()))
        elif isinstance(node, NodeView):
            results.append(1)
        elif isinstance(node, (list, dict, str)):
            results.append(len(node))
        else:
            results.append(1)
    return results
