"""AST-validated restricted eval for the hq query language."""

import ast
from typing import Any, Dict


class UnsafeExpressionError(Exception):
    """Raised when an expression contains disallowed constructs."""


_ALLOWED_NODES = {
    # Expression wrapper
    ast.Expression,
    # Core access patterns
    ast.Attribute,
    ast.Subscript,
    ast.Call,
    ast.Name,
    ast.Constant,
    ast.Starred,
    # Index/slice
    ast.Slice,
    # Literal collections (as arguments)
    ast.List,
    ast.Tuple,
    # Lambdas (for find_by_predicate, sorted key=, etc.)
    ast.Lambda,
    ast.arguments,
    ast.arg,
    # Keyword args
    ast.keyword,
    # Comparisons and boolean ops
    ast.Compare,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.Gt,
    ast.LtE,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.FloorDiv,
    ast.USub,
    ast.UAdd,
    # Context
    ast.Load,
}

_SAFE_CALLABLE_NAMES = frozenset(
    {
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "tuple",
        "type",
        "isinstance",
        "sorted",
        "reversed",
        "enumerate",
        "zip",
        "range",
        "min",
        "max",
        "print",
        "any",
        "all",
        "filter",
        "map",
        "hasattr",
        "getattr",
    }
)

_SAFE_BUILTINS = {
    name: (
        __builtins__[name]  # type: ignore[index]
        if isinstance(__builtins__, dict)
        else getattr(__builtins__, name)
    )
    for name in _SAFE_CALLABLE_NAMES
}
_SAFE_BUILTINS.update({"True": True, "False": False, "None": None})

_MAX_AST_DEPTH = 20
_MAX_NODE_COUNT = 200


def validate_expression(expr_str: str) -> ast.Expression:
    """Parse and validate a Python expression. Raises UnsafeExpressionError on violations."""
    try:
        tree = ast.parse(expr_str, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Syntax error: {exc}") from exc

    node_count = 0

    def _validate(node, depth=0):
        nonlocal node_count
        node_count += 1

        if depth > _MAX_AST_DEPTH:
            raise UnsafeExpressionError("Expression exceeds maximum depth")
        if node_count > _MAX_NODE_COUNT:
            raise UnsafeExpressionError("Expression exceeds maximum node count")

        if type(node) not in _ALLOWED_NODES:
            raise UnsafeExpressionError(f"{type(node).__name__} is not allowed")

        # Validate Call nodes
        if isinstance(node, ast.Call):
            func = node.func
            # Allow method calls (attr access)
            if isinstance(func, ast.Attribute):
                pass
            # Allow safe built-in names
            elif isinstance(func, ast.Name):
                if func.id not in _SAFE_CALLABLE_NAMES:
                    raise UnsafeExpressionError(f"Calling {func.id!r} is not allowed")
            else:
                raise UnsafeExpressionError(
                    "Only method calls and safe built-in calls are allowed"
                )

        for child in ast.iter_child_nodes(node):
            _validate(child, depth + 1)

    _validate(tree)
    return tree


def safe_eval(expr_str: str, variables: Dict[str, Any]) -> Any:
    """Validate, compile, and eval with restricted namespace."""
    tree = validate_expression(expr_str)
    code = compile(tree, "<hq>", "eval")
    namespace = dict(_SAFE_BUILTINS)
    namespace.update(variables)
    return eval(code, {"__builtins__": {}}, namespace)  # pylint: disable=eval-used
