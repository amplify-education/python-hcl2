# Advanced API Reference

This document covers the intermediate pipeline stages, programmatic document construction with `Builder`, and the full pipeline diagram. For basic `load`/`dump` usage and options, see [Getting Started](01_getting_started.md).

## Intermediate Pipeline Stages

The full pipeline looks like this:

```
Forward:  HCL2 Text → Lark Parse Tree → LarkElement Tree → Python Dict
Reverse:  Python Dict → LarkElement Tree → HCL2 Text
```

You can access each stage individually for advanced use cases.

### parse / parses — HCL2 text to LarkElement tree

```python
tree = hcl2.parses('x = 1')       # StartRule
tree = hcl2.parse(open("main.tf")) # StartRule
```

Pass `discard_comments=True` to strip comments during transformation.

### parse_to_tree / parses_to_tree — HCL2 text to raw Lark tree

```python
lark_tree = hcl2.parses_to_tree('x = 1')  # lark.Tree
```

### transform — raw Lark tree to LarkElement tree

```python
lark_tree = hcl2.parses_to_tree('x = 1')
tree = hcl2.transform(lark_tree)  # StartRule
```

### serialize — LarkElement tree to Python dict

```python
tree = hcl2.parses('x = 1')
data = hcl2.serialize(tree)
# or with options:
from hcl2 import SerializationOptions
data = hcl2.serialize(tree, serialization_options=SerializationOptions(with_meta=True))
```

### Metadata sidecar

By default the serializer reports what it knows about a body -- that it is a
block and its comments -- as `__is_block__`, `__comments__` and
`__inline_comments__` keys among the attributes. HCL reserves none of those names, so a document that
declares one loses either the attribute or the metadata. With
`metadata_sidecar=True` each body is an `HclDict` instead: a `dict` holding the
attributes and nothing else, with the metadata on `hcl_meta`.

```python
from hcl2 import HclDict, meta_of, SerializationOptions

data = hcl2.loads(text, serialization_options=SerializationOptions(metadata_sidecar=True))
body = data["resource"][0]['"aws_instance"']['"web"']
meta_of(body).is_block      # True
meta_of(body).comments      # [{"value": "..."}]
meta_of({"plain": "dict"})  # None
```

`copy()`, `copy.copy`, `copy.deepcopy`, pickling and `|` keep the metadata;
`dict(body)` and `{**body}` give the attributes alone. `dumps` accepts either
form, including a hand-built dict using the in-band keys.

### from_dict / from_json — Python dict or JSON to LarkElement tree

```python
tree = hcl2.from_dict(data)                   # StartRule
tree = hcl2.from_json('{"x": 1}')             # StartRule
```

Both accept optional `deserializer_options`, `formatter_options`, and `apply_format` (default `True`).

### reconstruct — LarkElement tree (or Lark tree) to HCL2 text

```python
tree = hcl2.from_dict(data)
text = hcl2.reconstruct(tree)
```

## Builder

The `Builder` class produces dicts with the correct `__is_block__` markers so that `dumps` can distinguish blocks from plain objects:

```python
import hcl2

doc = hcl2.Builder()
res = doc.block("resource", labels=["aws_instance", "web"],
                ami="abc-123", instance_type="t2.micro")
res.block("tags", Name="HelloWorld")

hcl_string = hcl2.dumps(doc.build())
```

Output:

```hcl
resource "aws_instance" "web" {
  ami           = "abc-123"
  instance_type = "t2.micro"

  tags {
    Name = "HelloWorld"
  }
}
```

### Builder.block()

```python
block(
    block_type: str,
    labels: Optional[List[str]] = None,
    __nested_builder__: Optional[Builder] = None,
    **attributes,
) -> Builder
```

Returns the child `Builder` for the new block, allowing chained calls.

## Pipeline Diagram

```
                        Forward Pipeline
                        ================
  HCL2 Text
      │
      ▼
  ┌──────────────────┐   parse_to_tree / parses_to_tree
  │ Lark Parse Tree  │
  └────────┬─────────┘
           │             transform
           ▼
  ┌──────────────────┐
  │ LarkElement Tree │   parse / parses  (shortcut: HCL2 text → here)
  └────────┬─────────┘
           │             serialize
           ▼
  ┌──────────────────┐
  │ Python Dict      │   load / loads  (shortcut: HCL2 text → here)
  └──────────────────┘


                        Reverse Pipeline
                        ================
  Python Dict / JSON
      │
      ▼
  ┌──────────────────┐   from_dict / from_json
  │ LarkElement Tree │
  └────────┬─────────┘
           │             reconstruct
           ▼
  ┌──────────────────┐
  │ HCL2 Text        │   dump / dumps  (shortcut: Python Dict / JSON → here)
  └──────────────────┘
```

## See Also

- [Getting Started](01_getting_started.md) — basic `load`/`dump` usage, options reference
- [Querying HCL (Python)](02_querying.md) — typed view facades and tree walking
- [hq Reference](04_hq.md) — query HCL files from the command line
