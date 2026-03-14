# Querying HCL (Python API)

The query system lets you navigate HCL documents by structure rather than serializing to dicts. This page covers the Python API; for the `hq` CLI tool, see [hq Reference](04_hq.md).

## Quick Start

```python
import hcl2

doc = hcl2.query('resource "aws_instance" "main" { ami = "abc-123" }')

for block in doc.blocks("resource"):
    print(block.block_type, block.name_labels)
    ami = block.attribute("ami")
    if ami:
        print(f"  ami = {ami.value}")
```

You can also parse from a file:

```python
from hcl2.query import DocumentView

doc = DocumentView.parse_file("main.tf")
```

## DocumentView

The entry point for queries. Wraps a `StartRule`.

```python
doc = DocumentView.parse(text)         # from string
doc = DocumentView.parse_file("main.tf")  # from file
doc = hcl2.query(text)                 # convenience alias
doc = hcl2.query(open("main.tf"))      # also accepts file objects
```

| Method / Property | Returns | Description |
|---|---|---|
| `body` | `BodyView` | The document body |
| `blocks(block_type?, *labels)` | `List[BlockView]` | Blocks matching type and optional labels |
| `attributes(name?)` | `List[AttributeView]` | Attributes, optionally filtered by name |
| `attribute(name)` | `AttributeView \| None` | Single attribute by name |

## BodyView

Wraps a `BodyRule`. Same filtering methods as `DocumentView`.

## BlockView

Wraps a `BlockRule`.

```python
block = doc.blocks("resource", "aws_instance")[0]
block.block_type    # "resource"
block.labels        # ["resource", "aws_instance", "main"]
block.name_labels   # ["aws_instance", "main"]
block.body          # BodyView
```

| Property / Method | Returns | Description |
|---|---|---|
| `block_type` | `str` | First label (the block type name) |
| `labels` | `List[str]` | All labels as plain strings |
| `name_labels` | `List[str]` | Labels after the block type (`labels[1:]`) |
| `body` | `BodyView` | The block body |
| `blocks(...)` | `List[BlockView]` | Nested blocks (delegates to body) |
| `attributes(...)` | `List[AttributeView]` | Nested attributes (delegates to body) |
| `attribute(name)` | `AttributeView \| None` | Single nested attribute |

## AttributeView

Wraps an `AttributeRule`.

```python
attr = doc.attribute("ami")
attr.name        # "ami"
attr.value       # '"abc-123"' (serialized Python value)
attr.value_node  # NodeView over the expression
```

## Container Views

### TupleView

Wraps a `TupleRule`. Access via `find_all` or by navigating to a tuple-valued attribute.

```python
from hcl2.query.containers import TupleView
from hcl2.walk import find_first
from hcl2.rules.containers import TupleRule

doc = DocumentView.parse('x = [1, 2, 3]\n')
node = find_first(doc.attribute("x").raw, TupleRule)
tv = TupleView(node)
len(tv)          # 3
tv[0]            # NodeView for the first element
tv.elements      # List[NodeView]
```

### ObjectView

Wraps an `ObjectRule`.

```python
from hcl2.query.containers import ObjectView
from hcl2.rules.containers import ObjectRule

node = find_first(doc.attribute("tags").raw, ObjectRule)
ov = ObjectView(node)
ov.keys           # ["Name", "Env"]
ov.get("Name")    # NodeView for the value
ov.entries        # List[Tuple[str, NodeView]]
```

## Expression Views

### ForTupleView / ForObjectView

Wraps `ForTupleExprRule` / `ForObjectExprRule`.

```python
from hcl2.query.for_exprs import ForTupleView
from hcl2.rules.for_expressions import ForTupleExprRule

doc = DocumentView.parse('x = [for item in var.list : item]\n')
node = find_first(doc.raw, ForTupleExprRule)
fv = ForTupleView(node)
fv.iterator_name         # "item"
fv.second_iterator_name  # None (or "v" for "k, v in ...")
fv.iterable              # NodeView
fv.value_expr            # NodeView
fv.has_condition         # bool
fv.condition             # NodeView | None
```

`ForObjectView` adds `key_expr` and `has_ellipsis`.

### ConditionalView

Wraps a `ConditionalRule` (ternary `condition ? true : false`).

```python
from hcl2.query.expressions import ConditionalView
from hcl2.rules.expressions import ConditionalRule

doc = DocumentView.parse('x = var.enabled ? "on" : "off"\n')
node = find_first(doc.raw, ConditionalRule)
cv = ConditionalView(node)
cv.condition   # NodeView over the condition expression
cv.true_val    # NodeView over the true branch
cv.false_val   # NodeView over the false branch
```

### FunctionCallView

Wraps a `FunctionCallRule`.

```python
from hcl2.query.functions import FunctionCallView
from hcl2.rules.functions import FunctionCallRule

doc = DocumentView.parse('x = length(var.list)\n')
node = find_first(doc.raw, FunctionCallRule)
fv = FunctionCallView(node)
fv.name           # "length"
fv.args           # List[NodeView]
fv.has_ellipsis   # bool
```

## Common NodeView Methods

All view classes inherit from `NodeView`:

| Method / Property | Returns | Description |
|---|---|---|
| `raw` | `LarkElement` | The underlying IR node |
| `parent_view` | `NodeView \| None` | View over the parent node |
| `to_hcl()` | `str` | Reconstruct this subtree as HCL text |
| `to_dict(options?)` | `Any` | Serialize to a Python value |
| `find_all(rule_type)` | `List[NodeView]` | Find descendants by rule class |
| `find_by_predicate(fn)` | `List[NodeView]` | Find descendants where `fn(view)` is truthy |
| `walk_semantic()` | `List[NodeView]` | All semantic descendant nodes |
| `walk_rules()` | `List[NodeView]` | All rule descendant nodes |

## Tree Walking Primitives

The `hcl2.walk` module provides free functions for traversing the IR tree directly (without view wrappers):

```python
from hcl2.walk import walk, walk_rules, walk_semantic, find_all, find_first, ancestors
from hcl2.rules.base import AttributeRule

tree = hcl2.parses('x = 1\ny = 2\n')

# All nodes depth-first (including tokens)
for node in walk(tree):
    print(node)

# Only LarkRule nodes
for rule in walk_rules(tree):
    print(rule)

# Only semantic rules (skip NewLineOrCommentRule)
for rule in walk_semantic(tree):
    print(rule)

# Find specific rule types
attrs = list(find_all(tree, AttributeRule))
first_attr = find_first(tree, AttributeRule)

# Walk up the parent chain
for parent in ancestors(first_attr):
    print(parent)
```

## Next Steps

- [hq Reference](04_hq.md) — query HCL files from the command line
- [Advanced API Reference](03_advanced_api.md) — intermediate pipeline stages, Builder
- [Getting Started](01_getting_started.md) — core API (`load`/`dump`), options, CLI converters
