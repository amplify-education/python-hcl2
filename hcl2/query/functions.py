"""FunctionCallView facade."""

from typing import List

from hcl2.query._base import NodeView, register_view, view_for
from hcl2.rules.functions import FunctionCallRule


@register_view(FunctionCallRule)
class FunctionCallView(NodeView):
    """View over an HCL2 function call (FunctionCallRule)."""

    @property
    def name(self) -> str:
        """Return the function name (namespace::name joined)."""
        node: FunctionCallRule = self._node  # type: ignore[assignment]
        return "::".join(ident.serialize() for ident in node.identifiers)

    @property
    def args(self) -> List[NodeView]:
        """Return the function arguments as views."""
        node: FunctionCallRule = self._node  # type: ignore[assignment]
        args_rule = node.arguments
        if args_rule is None:
            return []
        return [view_for(arg) for arg in args_rule.arguments]

    @property
    def has_ellipsis(self) -> bool:
        """Return whether the argument list ends with ellipsis."""
        node: FunctionCallRule = self._node  # type: ignore[assignment]
        args_rule = node.arguments
        if args_rule is None:
            return False
        return args_rule.has_ellipsis
