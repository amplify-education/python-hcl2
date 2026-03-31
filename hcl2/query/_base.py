"""Base view class and registry for query facades."""

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
)

from hcl2.rules.abstract import LarkElement, LarkRule
from hcl2.utils import SerializationOptions
from hcl2 import walk as _walk_mod

T = TypeVar("T", bound=LarkRule)

_VIEW_REGISTRY: Dict[Type[LarkElement], Type["NodeView"]] = {}


def register_view(rule_type: Type[LarkElement]):
    """Class decorator: register a view class for a given rule type."""

    def decorator(cls):
        _VIEW_REGISTRY[rule_type] = cls
        return cls

    return decorator


def view_for(node: LarkElement) -> "NodeView":
    """Factory: dispatch by type, walk MRO for base matches, fallback to NodeView."""
    node_type = type(node)
    # Direct match
    if node_type in _VIEW_REGISTRY:
        return _VIEW_REGISTRY[node_type](node)
    # Walk MRO
    for base in node_type.__mro__:
        if base in _VIEW_REGISTRY:
            return _VIEW_REGISTRY[base](node)
    return NodeView(node)


class NodeView:
    """Base view wrapping a LarkElement node."""

    def __init__(self, node: LarkElement):
        self._node = node

    @property
    def raw(self) -> LarkElement:
        """Return the underlying IR node."""
        return self._node

    @property
    def parent_view(self) -> Optional["NodeView"]:
        """Return a view over the parent node, or None."""
        parent = getattr(self._node, "_parent", None)
        if parent is None:
            return None
        return view_for(parent)

    def find_all(self, rule_type: Type[T]) -> List["NodeView"]:
        """Find all descendants matching a rule class, returned as views."""
        return [view_for(n) for n in _walk_mod.find_all(self._node, rule_type)]

    def find_by_predicate(self, predicate: Callable[..., bool]) -> List["NodeView"]:
        """Find descendants matching a predicate on their views."""
        results = []
        for element in _walk_mod.walk_semantic(self._node):
            wrapped = view_for(element)
            if predicate(wrapped):
                results.append(wrapped)
        return results

    def walk_semantic(self) -> List["NodeView"]:
        """Return all semantic descendant nodes as views."""
        return [view_for(n) for n in _walk_mod.walk_semantic(self._node)]

    def walk_rules(self) -> List["NodeView"]:
        """Return all rule descendant nodes as views."""
        return [view_for(n) for n in _walk_mod.walk_rules(self._node)]

    def to_hcl(self) -> str:
        """Reconstruct this subtree as HCL text."""
        from hcl2.reconstructor import HCLReconstructor

        reconstructor = HCLReconstructor()
        return reconstructor.reconstruct_fragment(self._node)

    def to_dict(self, options: Optional[SerializationOptions] = None) -> Any:
        """Serialize this node to a Python value."""
        if options is not None:
            return self._node.serialize(options=options)
        return self._node.serialize()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} wrapping {self._node!r}>"


VIEW_TYPE_NAMES = {
    "DocumentView": "document",
    "BodyView": "body",
    "BlockView": "block",
    "AttributeView": "attribute",
    "TupleView": "tuple",
    "ObjectView": "object",
    "ForTupleView": "for_tuple",
    "ForObjectView": "for_object",
    "FunctionCallView": "function_call",
    "ConditionalView": "conditional",
    "NodeView": "node",
}


def view_type_name(node: "NodeView") -> str:
    """Return a short type name string for a view node."""
    cls_name = type(node).__name__
    return VIEW_TYPE_NAMES.get(cls_name, cls_name.lower())
