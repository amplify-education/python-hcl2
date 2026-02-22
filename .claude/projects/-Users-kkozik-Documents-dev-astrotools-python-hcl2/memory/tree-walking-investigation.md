# Tree Walking & Editing — Investigation Notes

## Context

Investigating "power-user" features for walking/editing the parsed LarkElement tree.

## Two Uncommitted Approaches Found

### 1. `hcl2/processor.py` — `RulesProcessor` (Selenium-like wrapper)

Already fleshed out. Wraps a `LarkRule` node, returns new `RulesProcessor` instances (chainable).

**Capabilities:**

- **Search:** `find_blocks()`, `find_attributes()`, `find_rules()`, `find_by_predicate()`
- **Walk:** `walk()` generator yielding `(processor, children)` tuples
- **Navigate:** `next()`, `previous()`, `siblings`, `next_siblings`, `previous_siblings`
- **Mutate:** `replace(new_node)`, `append_child(new_node)`
- Commented out: `insert_before()`

### 2. `hcl2/editor.py` — `Editor` with `TreePath` (XPath-like navigation)

Embryonic. `TreePath` = list of `(rule_name, index)` steps. Has debug `print()` statements. `visit()` method sketched but commented out.

## Recommendation: Selenium-style (`RulesProcessor`) wins

**Why it fits:**

- Tree is heterogeneous — chainable typed wrappers that "find, then act" match well
- Users want semantic searches (find blocks by label, attributes by name) — Selenium's `find_element_by_*` pattern
- Fluent chaining: `proc.find_block(["resource", "aws_instance"]).attribute("ami").replace(new_value)`
- Already handles skipping whitespace/comment nodes during navigation

**Why XPath-style (`Editor`) doesn't fit:**

- Paths are fragile — depend on exact tree structure and child indices
- Users shouldn't need to know `attribute → expr_term → expression → literal` path structure
- Doesn't compose with searches — purely positional

## Gaps in `RulesProcessor` Before It's a Complete Power-User API

1. **Missing mutations:** `insert_before()` / `insert_after()` / `remove()` / `delete()`
1. **Not exposed in `api.py`** — no public entry point
1. **No `__repr__`** — hard to inspect interactively
1. **No Builder integration** — no easy way to construct replacement nodes inline
1. **`walk()` quirk** — wraps all children including `None` and tokens, can be awkward
1. **Naming** — could become `HCLNavigator` or `TreeCursor` for public surface

## Key Architecture Context

- `LarkElement` (ABC) → `LarkToken` (terminals) and `LarkRule` (non-terminals)
- Bidirectional parent-child refs auto-set in `LarkRule.__init__`
- ~41 rule classes across 7 domain files
- Primitive mutation: `LarkToken.set_value()`, direct `_children` list mutation
