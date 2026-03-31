"""Structural path resolver for the hq query language."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, cast

from hcl2 import walk as _walk_mod
from hcl2.query._base import NodeView
from hcl2.query.path import PathSegment

if TYPE_CHECKING:
    from hcl2.query.blocks import BlockView


@dataclass
class _ResolverState:
    """Tracks position within multi-label blocks during resolution."""

    node: NodeView
    label_depth: int = 0  # how many block labels consumed so far


def resolve_path(root: NodeView, segments: List[PathSegment]) -> List[NodeView]:
    """Resolve a structural path against a document view."""
    if not segments:
        return [root]

    states = [_ResolverState(node=root)]

    for segment in segments:
        next_states: List[_ResolverState] = []

        if segment.recursive:
            # Recursive descent: collect all descendants, then match
            for state in states:
                next_states.extend(_resolve_recursive(state, segment))
        else:
            for state in states:
                next_states.extend(_resolve_segment(state, segment))

        states = next_states
        if not states:
            return []

    return [s.node for s in states]


def _resolve_segment(  # pylint: disable=too-many-return-statements
    state: _ResolverState, segment: PathSegment
) -> List[_ResolverState]:
    """Resolve a single segment against a state."""
    from hcl2.query.attributes import AttributeView
    from hcl2.query.blocks import BlockView
    from hcl2.query.body import BodyView, DocumentView
    from hcl2.query.containers import ObjectView, TupleView
    from hcl2.query.expressions import ConditionalView
    from hcl2.query.functions import FunctionCallView

    node = state.node

    # DocumentView/BodyView: look up blocks and attributes by name
    if isinstance(node, (DocumentView, BodyView)):
        return _resolve_on_body(node, segment)

    # BlockView with unconsumed labels
    if isinstance(node, BlockView) and state.label_depth < len(node.name_labels):
        return _resolve_on_block_labels(node, segment, state.label_depth)

    # BlockView with labels consumed: delegate to body
    if isinstance(node, BlockView):
        return _resolve_on_body(node.body, segment)

    # AttributeView: unwrap to value_node
    if isinstance(node, AttributeView):
        value_view = node.value_node
        return _resolve_segment(_ResolverState(node=value_view), segment)

    # ExprTermRule wrapper: unwrap to inner rule
    if _is_expr_term(node):
        inner = _unwrap_expr_term(node)
        if inner is not None:
            return _resolve_segment(_ResolverState(node=inner), segment)
        return []

    # ObjectView
    if isinstance(node, ObjectView):
        return _resolve_on_object(node, segment)

    # TupleView
    if isinstance(node, TupleView):
        return _resolve_on_tuple(node, segment)

    # FunctionCallView: resolve .args and .name
    if isinstance(node, FunctionCallView):
        return _resolve_on_function_call(node, segment)

    # ConditionalView: resolve .condition, .true_val, .false_val
    if isinstance(node, ConditionalView):
        return _resolve_on_conditional(node, segment)

    return []


def _resolve_recursive(
    state: _ResolverState, segment: PathSegment
) -> List[_ResolverState]:
    """Recursive descent: try matching segment on the node and all descendants."""
    from hcl2.query._base import view_for

    results: List[_ResolverState] = []
    seen_ids: set = set()

    # Collect all descendant views to try matching against
    candidates = [state]
    for element in _walk_mod.walk_semantic(state.node._node):
        wrapped = view_for(element)
        candidates.append(_ResolverState(node=wrapped))

    if segment.type_filter is not None:
        # Type-qualified matching: match by type and name directly
        results = _match_by_type_and_name(candidates, segment, seen_ids)
    else:
        non_recursive = PathSegment(
            name=segment.name,
            select_all=segment.select_all,
            index=segment.index,
            recursive=False,
            predicate=segment.predicate,
            type_filter=None,
        )
        for candidate in candidates:
            for match in _resolve_segment(candidate, non_recursive):
                node_id = id(match.node._node)
                if node_id not in seen_ids:
                    seen_ids.add(node_id)
                    results.append(match)

    return _apply_index_filter(results, segment)


def _match_by_type_and_name(
    candidates: List[_ResolverState], segment: PathSegment, seen_ids: set
) -> List[_ResolverState]:
    """Match candidates by type filter and name property."""
    from hcl2.query._base import view_type_name

    results: List[_ResolverState] = []
    for candidate in candidates:
        node = candidate.node
        type_name = view_type_name(node)
        if type_name != segment.type_filter:
            continue

        # Check name match
        if segment.name == "*" or _node_matches_name(node, segment.name):
            node_id = id(node._node)
            if node_id not in seen_ids:
                seen_ids.add(node_id)
                results.append(candidate)

    return results


def _node_matches_name(node: NodeView, name: str) -> bool:
    """Check if a node's name property matches the given name."""
    node_name = getattr(node, "name", None)
    if node_name is not None:
        return node_name == name
    # BlockView: check block_type
    block_type = getattr(node, "block_type", None)
    if block_type is not None:
        return block_type == name
    return False


def _resolve_on_body(node: NodeView, segment: PathSegment) -> List[_ResolverState]:
    """Resolve a segment on a DocumentView or BodyView."""
    from hcl2.query.body import BodyView, DocumentView

    # Get the actual body view for delegation
    if isinstance(node, DocumentView):
        body = node.body
    elif isinstance(node, BodyView):
        body = node
    else:
        return []

    candidates: List[_ResolverState] = []

    if segment.name == "*":
        # Wildcard: all blocks and attributes
        for blk in body.blocks():
            blk_view = cast("BlockView", blk)
            depth = len(blk_view.name_labels) if segment.skip_labels else 0
            candidates.append(_ResolverState(node=blk, label_depth=depth))
        for attr in body.attributes():
            candidates.append(_ResolverState(node=attr))
    else:
        # Match block types
        for blk in body.blocks(segment.name):
            blk_view = cast("BlockView", blk)
            depth = len(blk_view.name_labels) if segment.skip_labels else 0
            candidates.append(_ResolverState(node=blk, label_depth=depth))
        # Match attribute names
        for attr in body.attributes(segment.name):
            candidates.append(_ResolverState(node=attr))

    return _apply_index_filter(candidates, segment)


def _resolve_on_block_labels(
    node: "NodeView", segment: PathSegment, label_depth: int
) -> List[_ResolverState]:
    """Resolve a segment against unconsumed block labels."""
    from hcl2.query.blocks import BlockView

    # Type-qualified segments (e.g. tuple:*) never match labels
    if segment.type_filter is not None:
        return []

    block: BlockView = node  # type: ignore[assignment]
    name_labels = block.name_labels

    if segment.name == "*":
        # Wildcard matches any label
        return [_ResolverState(node=block, label_depth=label_depth + 1)]

    if label_depth < len(name_labels) and name_labels[label_depth] == segment.name:
        return [_ResolverState(node=block, label_depth=label_depth + 1)]

    return []


def _resolve_on_object(node: "NodeView", segment: PathSegment) -> List[_ResolverState]:
    """Resolve a segment on an ObjectView."""
    from hcl2.query.containers import ObjectView

    obj: ObjectView = node  # type: ignore[assignment]

    if segment.name == "*":
        candidates = [_ResolverState(node=v) for _, v in obj.entries]
        return _apply_index_filter(candidates, segment)

    val = obj.get(segment.name)
    if val is not None:
        return [_ResolverState(node=val)]
    return []


def _resolve_on_tuple(node: "NodeView", segment: PathSegment) -> List[_ResolverState]:
    """Resolve a segment on a TupleView."""
    from hcl2.query.containers import TupleView

    tup: TupleView = node  # type: ignore[assignment]

    if segment.select_all:
        return [_ResolverState(node=elem) for elem in tup.elements]

    if segment.index is not None:
        try:
            elem = tup[segment.index]
            return [_ResolverState(node=elem)]
        except IndexError:
            return []

    return []


def _resolve_on_function_call(
    node: "NodeView", segment: PathSegment
) -> List[_ResolverState]:
    """Resolve a segment on a FunctionCallView."""
    from hcl2.query.functions import FunctionCallView

    func: FunctionCallView = node  # type: ignore[assignment]

    if segment.name == "args":
        args = func.args
        candidates = [_ResolverState(node=arg) for arg in args]
        return _apply_index_filter(candidates, segment)

    return []


def _resolve_on_conditional(
    node: "NodeView", segment: PathSegment
) -> List[_ResolverState]:
    """Resolve a segment on a ConditionalView."""
    from hcl2.query.expressions import ConditionalView

    cond: ConditionalView = node  # type: ignore[assignment]

    if segment.name == "condition":
        return [_ResolverState(node=cond.condition)]
    if segment.name == "true_val":
        return [_ResolverState(node=cond.true_val)]
    if segment.name == "false_val":
        return [_ResolverState(node=cond.false_val)]

    return []


def _apply_index_filter(
    candidates: List[_ResolverState], segment: PathSegment
) -> List[_ResolverState]:
    """Apply type filter, predicate filter, and [*]/[N] index to candidates."""
    # Apply type filter if present
    if segment.type_filter is not None:
        from hcl2.query._base import view_type_name

        candidates = [
            c for c in candidates if view_type_name(c.node) == segment.type_filter
        ]

    # Apply predicate filter if present
    if segment.predicate is not None:
        from hcl2.query.predicate import evaluate_predicate

        pred = segment.predicate
        candidates = [
            c
            for c in candidates
            if evaluate_predicate(pred, c.node)  # type: ignore[arg-type]
        ]

    if segment.select_all:
        return candidates
    if segment.index is not None:
        if 0 <= segment.index < len(candidates):
            return [candidates[segment.index]]
        return []
    return candidates


def _is_expr_term(node: NodeView) -> bool:
    """Check if a node wraps an ExprTermRule."""
    from hcl2.rules.expressions import ExprTermRule

    return isinstance(node._node, ExprTermRule)


def _unwrap_expr_term(node: NodeView):
    """Unwrap ExprTermRule to a view over its inner rule."""
    from hcl2.query._base import view_for
    from hcl2.rules.expressions import ExprTermRule

    expr_term: ExprTermRule = node._node  # type: ignore[assignment]
    inner = expr_term.expression
    if inner is not None:
        return view_for(inner)
    return None
