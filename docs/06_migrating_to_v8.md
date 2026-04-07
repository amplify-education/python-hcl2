# Migrating to v8

This guide covers breaking changes when upgrading from python-hcl2 v7 to v8. Changes are ordered by likelihood of impact — if you only use `load()`/`loads()` to read HCL files, focus on the first three sections.

## String values now include HCL quotes

**Impact: high** — silently changes output without raising errors.

In v7, `load()` stripped the surrounding double-quotes from HCL string values. In v8, quotes are preserved by default to enable lossless round-trips.

```python
# Given: name = "hello"

# v7
data["name"]  # 'hello'

# v8 (default)
data["name"]  # '"hello"'
```

To restore v7 behavior:

```python
import hcl2
from hcl2 import SerializationOptions

data = hcl2.load(f, serialization_options=SerializationOptions(strip_string_quotes=True))
```

> **Note:** `strip_string_quotes=True` is one-way — dicts produced with it cannot round-trip back to HCL via `dumps()` because the quotes needed to distinguish strings from identifiers are gone.

## New metadata keys in output dicts

**Impact: high** — code that iterates keys or does exact-match assertions will break.

v8 adds two new key categories to output dicts by default:

| Key | Default | Purpose |
|---|---|---|
| `__is_block__` | on (`explicit_blocks=True`) | Distinguishes HCL blocks from plain objects |
| `__comments__`, `__inline_comments__` | on (`with_comments=True`) | Preserves HCL comments |

To suppress them:

```python
opts = SerializationOptions(explicit_blocks=False, with_comments=False)
data = hcl2.load(f, serialization_options=opts)
```

> **Note:** `explicit_blocks=False` disables round-trip support via `dumps()` — the deserializer needs `__is_block__` markers to reconstruct blocks correctly.

The v7 metadata keys `__start_line__` and `__end_line__` are still available but remain opt-in:

```python
opts = SerializationOptions(with_meta=True)
```

## `load()` / `loads()` signature changed

**Impact: high** — calls using `with_meta` will raise `TypeError`.

The `with_meta` positional/keyword parameter has been replaced by a `SerializationOptions` object:

```python
# v7
data = hcl2.load(f, with_meta=True)
data = hcl2.loads(text, with_meta=True)

# v8
from hcl2 import SerializationOptions
data = hcl2.load(f, serialization_options=SerializationOptions(with_meta=True))
data = hcl2.loads(text, serialization_options=SerializationOptions(with_meta=True))
```

All parameters on `load()`/`loads()` are now keyword-only.

## `reverse_transform()` and `writes()` removed

**Impact: medium** — calls will raise `ImportError` / `AttributeError`.

The v7 two-step dict-to-HCL workflow has been replaced by `dump()`/`dumps()`:

```python
# v7
ast = hcl2.reverse_transform(data)
text = hcl2.writes(ast)

# v8
text = hcl2.dumps(data)

# or to a file:
with open("output.tf", "w") as f:
    hcl2.dump(data, f)
```

`dumps()` accepts optional `deserializer_options` and `formatter_options` for controlling the output:

```python
from hcl2 import DeserializerOptions, FormatterOptions

text = hcl2.dumps(
    data,
    deserializer_options=DeserializerOptions(object_elements_colon=True),
    formatter_options=FormatterOptions(indent_length=4),
)
```

## `parse()` / `parses()` return type changed

**Impact: medium** — code accessing Lark tree internals will break.

These functions now return a typed `StartRule` (a `LarkElement` node) instead of a raw `lark.Tree`:

```python
# v7
tree = hcl2.parses(text)  # -> lark.Tree
tree.data                  # 'start'
tree.children              # [lark.Tree, ...]

# v8
tree = hcl2.parses(text)  # -> StartRule
tree.body                  # typed BodyRule accessor
```

If you need the raw Lark tree, use the new explicit functions:

```python
lark_tree = hcl2.parses_to_tree(text)   # -> lark.Tree (raw)
rule_tree = hcl2.transform(lark_tree)    # -> StartRule (typed)
```

## `transform()` signature and return type changed

**Impact: medium** — same cause as above.

```python
# v7
data = hcl2.transform(ast, with_meta=True)  # -> dict

# v8
rule_tree = hcl2.transform(lark_tree, discard_comments=False)  # -> StartRule
data = hcl2.serialize(rule_tree, serialization_options=opts)     # -> dict
```

In v8, `transform()` produces a typed IR tree. To get a dict, follow it with `serialize()`.

## `DictTransformer` and `reconstruction_parser` removed

**Impact: low** — only affects code importing internals.

| v7 import | v8 replacement |
|---|---|
| `from hcl2.transformer import DictTransformer` | Use `hcl2.transform()` + `hcl2.serialize()` |
| `from hcl2.parser import reconstruction_parser` | Use `hcl2.parser.parser()` (single parser) |
| `from hcl2.reconstructor import HCLReverseTransformer` | Use `hcl2.from_dict()` + `hcl2.reconstruct()` |

## New pipeline stages

v8 exposes the full bidirectional pipeline as composable functions:

```
Forward:  HCL text -> parses_to_tree() -> transform() -> serialize() -> dict
Reverse:  dict -> from_dict() -> reconstruct() -> HCL text
```

| Function | Input | Output |
|---|---|---|
| `parses_to_tree(text)` | HCL string | raw `lark.Tree` |
| `transform(lark_tree)` | `lark.Tree` | `StartRule` |
| `serialize(tree)` | `StartRule` | `dict` |
| `from_dict(data)` | `dict` | `StartRule` |
| `from_json(text)` | JSON string | `StartRule` |
| `reconstruct(tree)` | `StartRule` | HCL string |

## CLI changes

The `hcl2tojson` entry point moved from `hcl2.__main__:main` to `cli.hcl_to_json:main`. A shim keeps `python -m hcl2` working, but direct imports from `hcl2.__main__` should be updated.

Two new CLI tools ship with v8:

- **`jsontohcl2`** — convert JSON back to HCL2, with diff/dry-run support
- **`hq`** — structural query tool for HCL files (jq-like syntax)

## Python 3.7 no longer supported

The minimum Python version is now **3.8**.

## Quick reference: v7-compatible defaults

If you want v8 to behave as closely to v7 as possible:

```python
import hcl2
from hcl2 import SerializationOptions

V7_COMPAT = SerializationOptions(
    strip_string_quotes=True,
    explicit_blocks=False,
    with_comments=False,
)

data = hcl2.load(f, serialization_options=V7_COMPAT)
```

This restores the v7 dict shape but disables round-trip support and comment preservation.
