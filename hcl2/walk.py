"""Generic tree-walking primitives for the LarkElement IR tree."""

from typing import Callable, Iterator, Optional, Type, TypeVar

from hcl2.rules.abstract import LarkElement, LarkRule
from hcl2.rules.whitespace import NewLineOrCommentRule

T = TypeVar("T", bound=LarkElement)


def walk(node: LarkElement) -> Iterator[LarkElement]:
    """Depth-first pre-order traversal yielding all nodes including tokens."""
    yield node
    if isinstance(node, LarkRule):
        for child in node.children:
            if child is not None:
                yield from walk(child)


def walk_rules(node: LarkElement) -> Iterator[LarkRule]:
    """Walk yielding only LarkRule nodes (skip LarkTokens)."""
    for element in walk(node):
        if isinstance(element, LarkRule):
            yield element


def walk_semantic(node: LarkElement) -> Iterator[LarkRule]:
    """Walk yielding only semantic LarkRule nodes (skip tokens and whitespace/comments)."""
    for element in walk_rules(node):
        if not isinstance(element, NewLineOrCommentRule):
            yield element


def find_all(node: LarkElement, rule_type: Type[T]) -> Iterator[T]:
    """Find all descendants matching a rule class (semantic walk)."""
    for element in walk_semantic(node):
        if isinstance(element, rule_type):
            yield element


def find_first(node: LarkElement, rule_type: Type[T]) -> Optional[T]:
    """Find first descendant matching a rule class, or None."""
    for element in find_all(node, rule_type):
        return element
    return None


def find_by_predicate(
    node: LarkElement, predicate: Callable[[LarkElement], bool]
) -> Iterator[LarkElement]:
    """Find all descendants matching an arbitrary predicate."""
    for element in walk(node):
        if predicate(element):
            yield element


def ancestors(node: LarkElement) -> Iterator[LarkElement]:
    """Walk up the parent chain (excludes node itself)."""
    current = getattr(node, "_parent", None)
    while current is not None:
        yield current
        current = getattr(current, "_parent", None)
