"""Self-contained recursive descent parser and evaluator for select() predicates.

Predicate grammar::

    predicate  := or_expr
    or_expr    := and_expr ("or" and_expr)*
    and_expr   := not_expr ("and" not_expr)*
    not_expr   := "not" not_expr | comparison
    comparison := accessor (comp_op literal)? | any_all | has_expr
    any_all    := ("any" | "all") "(" accessor ";" predicate ")"
    has_expr   := "has" "(" STRING ")"
    accessor   := "." IDENT ("." IDENT)* ("[" INT "]")? ("|" BUILTIN_OR_FUNC)?
    BUILTIN    := "keys" | "values" | "length" | "not"
    FUNC       := ("contains" | "test" | "startswith" | "endswith") "(" STRING ")"
    literal    := STRING | NUMBER | "true" | "false" | "null"
    comp_op    := "==" | "!=" | "<" | ">" | "<=" | ">="

No Python eval() is used.
"""

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Union

from hcl2.query.path import QuerySyntaxError


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


_STRING_FUNCTIONS = frozenset({"contains", "test", "startswith", "endswith"})


@dataclass(frozen=True)
class Accessor:
    """A dotted accessor, e.g. ``.foo.bar[0]`` or ``.foo | length``."""

    parts: List[str]  # ["foo", "bar"]
    index: Optional[int] = None  # [0] suffix
    builtin: Optional[str] = None  # "length", "keys", "values", "not"
    builtin_arg: Optional[str] = None  # argument for string functions


@dataclass(frozen=True)
class Comparison:
    """``accessor comp_op literal`` or bare ``accessor`` (existence check)."""

    accessor: Accessor
    operator: Optional[str] = None  # "==", "!=", "<", ">", "<=", ">="
    value: Any = None  # Python literal value


@dataclass(frozen=True)
class NotExpr:
    """``not expr``."""

    child: Any  # PredicateNode


@dataclass(frozen=True)
class AndExpr:
    """``expr and expr ...``."""

    children: List[Any]


@dataclass(frozen=True)
class OrExpr:
    """``expr or expr ...``."""

    children: List[Any]


@dataclass(frozen=True)
class AnyExpr:
    """``any(accessor; predicate)`` — true if any element matches."""

    accessor: "Accessor"
    predicate: Any  # PredicateNode


@dataclass(frozen=True)
class AllExpr:
    """``all(accessor; predicate)`` — true if all elements match."""

    accessor: "Accessor"
    predicate: Any  # PredicateNode


@dataclass(frozen=True)
class HasExpr:
    """``has("key")`` — true if the key exists on the target."""

    key: str


PredicateNode = Union[Comparison, NotExpr, AndExpr, OrExpr, AnyExpr, AllExpr, HasExpr]


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<DOT>\.)
    | (?P<PIPE>\|)
    | (?P<SEMI>;)
    | (?P<LPAREN>\()
    | (?P<RPAREN>\))
    | (?P<LBRACKET>\[)
    | (?P<RBRACKET>\])
    | (?P<OP>==|!=|<=|>=|<|>)
    | (?P<STRING>"(?:[^"\\]|\\.)*")
    | (?P<NUMBER>-?[0-9]+(?:\.[0-9]+)?)
    | (?P<WORD>[a-zA-Z_][a-zA-Z0-9_-]*)
    | (?P<WS>\s+)
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    """A single token from the predicate tokeniser."""

    kind: str
    value: str


def tokenize(text: str) -> List[Token]:
    """Tokenize a predicate string."""
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise QuerySyntaxError(
                f"Unexpected character at position {pos} in predicate: {text!r}"
            )
        pos = match.end()
        kind = match.lastgroup
        assert kind is not None
        if kind == "WS":
            continue
        tokens.append(Token(kind=kind, value=match.group()))
    return tokens


# ---------------------------------------------------------------------------
# Recursive descent parser
# ---------------------------------------------------------------------------


class _Parser:  # pylint: disable=too-few-public-methods
    """Consumes token list and builds a predicate AST."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> Optional[Token]:
        """Return current token without consuming."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> Token:
        """Consume and return the current token."""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind: str) -> Token:
        """Consume token of *kind*, or raise."""
        tok = self._peek()
        if tok is None or tok.kind != kind:
            found = tok.value if tok else "end-of-input"
            raise QuerySyntaxError(f"Expected {kind}, got {found!r}")
        return self._advance()

    def parse(self) -> PredicateNode:
        """Parse the full token stream into a predicate AST."""
        node = self._or_expr()
        if self.pos < len(self.tokens):
            raise QuerySyntaxError(f"Unexpected token: {self.tokens[self.pos].value!r}")
        return node

    def _or_expr(self) -> PredicateNode:
        """Parse ``and_expr ('or' and_expr)*``."""
        children = [self._and_expr()]
        tok = self._peek()
        while tok and tok.kind == "WORD" and tok.value == "or":
            self._advance()
            children.append(self._and_expr())
            tok = self._peek()
        return children[0] if len(children) == 1 else OrExpr(children=children)

    def _and_expr(self) -> PredicateNode:
        """Parse ``not_expr ('and' not_expr)*``."""
        children = [self._not_expr()]
        tok = self._peek()
        while tok and tok.kind == "WORD" and tok.value == "and":
            self._advance()
            children.append(self._not_expr())
            tok = self._peek()
        return children[0] if len(children) == 1 else AndExpr(children=children)

    def _not_expr(self) -> PredicateNode:
        """Parse ``'not' not_expr | comparison``."""
        tok = self._peek()
        if tok and tok.kind == "WORD" and tok.value == "not":
            self._advance()
            return NotExpr(child=self._not_expr())
        return self._comparison()

    def _comparison(self) -> PredicateNode:
        """Parse ``accessor (comp_op literal)?``, ``any/all(...)``, or ``has(...)``."""
        tok = self._peek()
        if tok and tok.kind == "WORD" and tok.value in ("any", "all"):
            return self._any_all()

        if tok and tok.kind == "WORD" and tok.value == "has":
            return self._has_expr()

        accessor = self._accessor()
        tok = self._peek()
        if tok and tok.kind == "OP":
            comp_op = self._advance().value
            value = self._literal()
            return Comparison(accessor=accessor, operator=comp_op, value=value)
        return Comparison(accessor=accessor)

    def _has_expr(self) -> PredicateNode:
        """Parse ``has("key")``."""
        self._advance()  # consume "has"
        self._expect("LPAREN")
        key_tok = self._expect("STRING")
        key = key_tok.value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        self._expect("RPAREN")
        return HasExpr(key=key)

    def _any_all(self) -> PredicateNode:
        """Parse ``any(accessor; predicate)`` or ``all(accessor; predicate)``."""
        func_name = self._advance().value  # "any" or "all"
        self._expect("LPAREN")
        accessor = self._accessor()
        self._expect("SEMI")
        predicate = self._or_expr()
        self._expect("RPAREN")
        if func_name == "any":
            return AnyExpr(accessor=accessor, predicate=predicate)
        return AllExpr(accessor=accessor, predicate=predicate)

    def _accessor(self) -> Accessor:
        """Parse ``'.' IDENT ('.' IDENT)* ('[' INT ']')? ('|' BUILTIN)?``."""
        from hcl2.query.builtins import BUILTIN_NAMES

        parts: List[str] = []
        self._expect("DOT")
        parts.append(self._expect("WORD").value)

        tok = self._peek()
        while tok and tok.kind == "DOT":
            self._advance()
            parts.append(self._expect("WORD").value)
            tok = self._peek()

        # Optional [N] index
        index = None
        tok = self._peek()
        if tok and tok.kind == "LBRACKET":
            self._advance()
            num_tok = self._expect("NUMBER")
            index = int(num_tok.value)
            self._expect("RBRACKET")

        # Optional | builtin/function (e.g. ``| length``, ``| contains("x")``,
        # ``| not``)
        builtin = None
        builtin_arg = None
        tok = self._peek()
        if tok and tok.kind == "PIPE":
            self._advance()
            # Allow optional leading dot (jq-style ``| .length``)
            dot_tok = self._peek()
            if dot_tok and dot_tok.kind == "DOT":
                self._advance()
            word_tok = self._expect("WORD")
            if word_tok.value in _STRING_FUNCTIONS:
                builtin = word_tok.value
                self._expect("LPAREN")
                arg_tok = self._expect("STRING")
                builtin_arg = (
                    arg_tok.value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
                )
                self._expect("RPAREN")
            elif word_tok.value == "not":
                builtin = "not"
            elif word_tok.value in BUILTIN_NAMES:
                builtin = word_tok.value
            else:
                raise QuerySyntaxError(
                    f"Expected builtin or string function after |, "
                    f"got {word_tok.value!r}"
                )

        return Accessor(
            parts=parts, index=index, builtin=builtin, builtin_arg=builtin_arg
        )

    def _literal(self) -> Any:  # pylint: disable=too-many-return-statements
        """Parse a literal value (string, number, boolean, or null)."""
        tok = self._peek()
        if tok is None:
            raise QuerySyntaxError("Expected literal, got end-of-input")

        if tok.kind == "STRING":
            self._advance()
            return tok.value[1:-1].replace('\\"', '"').replace("\\\\", "\\")

        if tok.kind == "NUMBER":
            self._advance()
            if "." in tok.value:
                return float(tok.value)
            return int(tok.value)

        if tok.kind == "WORD":
            if tok.value == "true":
                self._advance()
                return True
            if tok.value == "false":
                self._advance()
                return False
            if tok.value == "null":
                self._advance()
                return None

        raise QuerySyntaxError(f"Expected literal, got {tok.value!r}")


def parse_predicate(text: str) -> PredicateNode:
    """Parse a predicate expression string into an AST."""
    tokens = tokenize(text)
    if not tokens:
        raise QuerySyntaxError("Empty predicate")
    return _Parser(tokens).parse()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def _resolve_accessor(  # pylint: disable=too-many-return-statements
    accessor: Accessor, target: Any
) -> Any:
    """Resolve an accessor path against a target (typically a NodeView)."""
    from hcl2.query._base import NodeView
    from hcl2.query.blocks import BlockView
    from hcl2.query.path import parse_path
    from hcl2.query.resolver import resolve_path

    current = target

    for part in accessor.parts:
        if current is None:
            return None

        # Virtual ".type" accessor — returns short type name string
        # Unwraps ExprTermRule so concrete inner type is reported.
        if part == "type" and isinstance(current, NodeView):
            from hcl2.query._base import view_for, view_type_name
            from hcl2.rules.expressions import ExprTermRule

            unwrapped = current
            if (
                type(current).__name__ == "NodeView"
                and isinstance(current._node, ExprTermRule)
                and current._node.expression is not None
            ):
                unwrapped = view_for(current._node.expression)
            current = view_type_name(unwrapped)
            continue

        # Try Python property first
        if isinstance(current, NodeView) and hasattr(type(current), part):
            prop = getattr(type(current), part, None)
            if isinstance(prop, property):
                current = getattr(current, part)
                continue

        # Try structural resolution
        if isinstance(current, NodeView):
            segments = parse_path(part)
            resolved = resolve_path(current, segments)
            # For BlockViews, if label matching fails, try the body directly
            if not resolved and isinstance(current, BlockView):
                resolved = resolve_path(current.body, segments)
            if not resolved:
                current = None
                break
            current = resolved[0] if len(resolved) == 1 else resolved
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            current = None
            break

    # Apply index
    if accessor.index is not None:
        if isinstance(current, (list, tuple)):
            if 0 <= accessor.index < len(current):
                current = current[accessor.index]
            else:
                return None
        elif hasattr(current, "__getitem__"):
            try:
                current = current[accessor.index]
            except (IndexError, KeyError):
                return None
        else:
            return None

    # Apply builtin transform (e.g. ``| length``, ``| contains("x")``, ``| not``)
    # Note: postfix not and string functions must run even when current is None
    if accessor.builtin is not None:
        if accessor.builtin == "not":
            return not (current is not None and current is not False and current != 0)
        if accessor.builtin_arg is not None:
            return _apply_string_function(
                accessor.builtin, accessor.builtin_arg, current
            )
        if current is not None:
            current = _apply_accessor_builtin(accessor.builtin, current)

    return current


def _coerce_str(value: Any) -> str:
    """Coerce a value to a string for string function matching."""
    from hcl2.query._base import NodeView

    if isinstance(value, NodeView):
        d = value.to_dict()
        if isinstance(d, str):
            return d
        return str(d)
    if isinstance(value, str):
        # Strip surrounding quotes from serialized HCL strings
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return value
    if value is None:
        return ""
    return str(value)


def _apply_string_function(name: str, arg: str, current: Any) -> bool:
    """Apply a string function (contains, test, startswith, endswith)."""
    if current is None:
        return False
    s = _coerce_str(current)
    if name == "contains":
        return arg in s
    if name == "startswith":
        return s.startswith(arg)
    if name == "endswith":
        return s.endswith(arg)
    if name == "test":
        try:
            return bool(re.search(arg, s))
        except re.error as exc:
            raise QuerySyntaxError(f"Invalid regex in test(): {exc}") from exc
    raise QuerySyntaxError(f"Unknown string function: {name!r}")


def _apply_accessor_builtin(name: str, value: Any) -> Any:
    """Apply a builtin transform inside a predicate accessor."""
    from hcl2.query.builtins import apply_builtin

    results = apply_builtin(name, [value])
    if results:
        return results[0]
    return None


_KEYWORD_MAP = {"true": True, "false": False, "null": None}


def _to_comparable(value: Any) -> Any:
    """Convert a NodeView to a comparable Python value."""
    from hcl2.query._base import NodeView

    if isinstance(value, NodeView):
        value = value.to_dict()
    # Coerce HCL keyword strings to Python types so that
    # ``select(.x == true)`` matches the HCL keyword ``true``.
    if isinstance(value, str) and value in _KEYWORD_MAP:
        return _KEYWORD_MAP[value]
    return value


_COMPARISON_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    ">=": lambda a, b: a >= b,
}


def evaluate_predicate(pred: PredicateNode, target: Any) -> bool:
    """Evaluate a predicate against a target (typically a NodeView)."""
    if isinstance(pred, HasExpr):
        return _evaluate_has(pred.key, target)

    if isinstance(pred, Comparison):
        resolved = _resolve_accessor(pred.accessor, target)
        if pred.operator is None:
            # String functions and postfix not return bool directly
            if isinstance(resolved, bool):
                return resolved
            # Existence / truthy check
            return resolved is not None and resolved is not False and resolved != 0
        left = _to_comparable(resolved)
        comp_fn = _COMPARISON_OPS.get(pred.operator)
        if comp_fn is None:
            raise QuerySyntaxError(f"Unknown operator: {pred.operator!r}")
        return comp_fn(left, pred.value)

    if isinstance(pred, NotExpr):
        return not evaluate_predicate(pred.child, target)

    if isinstance(pred, AndExpr):
        return all(evaluate_predicate(c, target) for c in pred.children)

    if isinstance(pred, OrExpr):
        return any(evaluate_predicate(c, target) for c in pred.children)

    if isinstance(pred, (AnyExpr, AllExpr)):
        return _evaluate_any_all(pred, target)

    raise QuerySyntaxError(f"Unknown predicate node type: {type(pred).__name__}")


def _evaluate_has(key: str, target: Any) -> bool:
    """Evaluate ``has("key")`` — check if a key exists on the target."""
    # Same as existence check for the given key
    accessor = Accessor(parts=[key])
    resolved = _resolve_accessor(accessor, target)
    return resolved is not None and resolved is not False and resolved != 0


def _evaluate_any_all(pred: Union[AnyExpr, AllExpr], target: Any) -> bool:
    """Evaluate ``any(accessor; predicate)`` or ``all(accessor; predicate)``."""
    resolved = _resolve_accessor(pred.accessor, target)
    if resolved is None:
        return isinstance(pred, AllExpr)  # all() on empty is True, any() is False

    # Ensure we iterate over a list
    if not isinstance(resolved, list):
        resolved = [resolved]

    check = all if isinstance(pred, AllExpr) else any
    return check(evaluate_predicate(pred.predicate, item) for item in resolved)
