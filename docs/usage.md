# python-hcl2 Usage Guide

## Quick Reference

| Function | Description |
|---|---|
| `hcl2.load(file)` | Parse an HCL2 file to a Python dict |
| `hcl2.loads(text)` | Parse an HCL2 string to a Python dict |
| `hcl2.dump(data, file)` | Write a Python dict as HCL2 to a file |
| `hcl2.dumps(data)` | Convert a Python dict to an HCL2 string |
| `hcl2.parse(file)` | Parse an HCL2 file to a LarkElement tree |
| `hcl2.parses(text)` | Parse an HCL2 string to a LarkElement tree |
| `hcl2.parse_to_tree(file)` | Parse an HCL2 file to a raw Lark tree |
| `hcl2.parses_to_tree(text)` | Parse an HCL2 string to a raw Lark tree |
| `hcl2.transform(lark_tree)` | Transform a raw Lark tree into a LarkElement tree |
| `hcl2.serialize(tree)` | Serialize a LarkElement tree to a Python dict |
| `hcl2.from_dict(data)` | Convert a Python dict into a LarkElement tree |
| `hcl2.from_json(text)` | Convert a JSON string into a LarkElement tree |
| `hcl2.reconstruct(tree)` | Convert a LarkElement tree (or Lark tree) to HCL2 text |
| `hcl2.Builder()` | Build HCL documents programmatically |

## HCL to Python dict

Use `load` / `loads` to parse HCL2 into a Python dictionary:

```python
import hcl2

with open("main.tf") as f:
    data = hcl2.load(f)

# or from a string
data = hcl2.loads('resource "aws_instance" "web" { ami = "abc-123" }')
```

### SerializationOptions

Pass `serialization_options` to control how the dict is produced:

```python
from hcl2 import loads, SerializationOptions

data = loads(text, serialization_options=SerializationOptions(
    with_meta=True,
    wrap_objects=True,
))
```

| Field | Type | Default | Description |
|---|---|---|---|
| `with_comments` | `bool` | `True` | Include comments in the output |
| `with_meta` | `bool` | `False` | Add `__start_line__` / `__end_line__` metadata |
| `wrap_objects` | `bool` | `False` | Wrap object values as inline HCL2 strings |
| `wrap_tuples` | `bool` | `False` | Wrap tuple values as inline HCL2 strings |
| `explicit_blocks` | `bool` | `True` | Add `__is_block__: True` markers to blocks |
| `preserve_heredocs` | `bool` | `True` | Keep heredocs in their original form |
| `force_operation_parentheses` | `bool` | `False` | Force parentheses around all operations |
| `preserve_scientific_notation` | `bool` | `True` | Keep scientific notation as-is |

## Python dict to HCL

Use `dump` / `dumps` to convert a Python dictionary back into HCL2 text:

```python
import hcl2

hcl_string = hcl2.dumps(data)

with open("output.tf", "w") as f:
    hcl2.dump(data, f)
```

### DeserializerOptions

Control how the dict is interpreted when building the LarkElement tree:

```python
from hcl2 import dumps, DeserializerOptions

text = dumps(data, deserializer_options=DeserializerOptions(
    object_elements_colon=True,
))
```

| Field | Type | Default | Description |
|---|---|---|---|
| `heredocs_to_strings` | `bool` | `False` | Convert heredocs to plain strings |
| `strings_to_heredocs` | `bool` | `False` | Convert strings with `\n` to heredocs |
| `object_elements_colon` | `bool` | `False` | Use `:` instead of `=` in object elements |
| `object_elements_trailing_comma` | `bool` | `True` | Add trailing commas in object elements |

### FormatterOptions

Control whitespace and alignment in the generated HCL2:

```python
from hcl2 import dumps, FormatterOptions

text = dumps(data, formatter_options=FormatterOptions(
    indent_length=4,
    vertically_align_attributes=False,
))
```

| Field | Type | Default | Description |
|---|---|---|---|
| `indent_length` | `int` | `2` | Number of spaces per indentation level |
| `open_empty_blocks` | `bool` | `True` | Expand empty blocks across multiple lines |
| `open_empty_objects` | `bool` | `True` | Expand empty objects across multiple lines |
| `open_empty_tuples` | `bool` | `False` | Expand empty tuples across multiple lines |
| `vertically_align_attributes` | `bool` | `True` | Vertically align `=` signs in attribute groups |
| `vertically_align_object_elements` | `bool` | `True` | Vertically align `=` signs in object elements |

## Building HCL from scratch

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

## Intermediate pipeline stages

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

## CLI Tools

### hcl2tojson

Convert HCL2 files to JSON.

```sh
hcl2tojson main.tf                  # print JSON to stdout
hcl2tojson main.tf output.json      # write to file
hcl2tojson terraform/ output/       # convert a directory
cat main.tf | hcl2tojson -          # read from stdin
```

**Flags:**

| Flag | Description |
|---|---|
| `-s` | Skip un-parsable files |
| `--json-indent N` | JSON indentation width (default: 2) |
| `--with-meta` | Add `__start_line__` / `__end_line__` metadata |
| `--with-comments` | Include comments in the output |
| `--wrap-objects` | Wrap object values as inline HCL2 |
| `--wrap-tuples` | Wrap tuple values as inline HCL2 |
| `--no-explicit-blocks` | Disable `__is_block__` markers |
| `--no-preserve-heredocs` | Convert heredocs to plain strings |
| `--force-parens` | Force parentheses around all operations |
| `--no-preserve-scientific` | Convert scientific notation to standard floats |
| `--version` | Show version and exit |

### jsontohcl2

Convert JSON files to HCL2.

```sh
jsontohcl2 output.json              # print HCL2 to stdout
jsontohcl2 output.json main.tf      # write to file
jsontohcl2 output/ terraform/       # convert a directory
cat output.json | jsontohcl2 -      # read from stdin
```

**Flags:**

| Flag | Description |
|---|---|
| `-s` | Skip un-parsable files |
| `--indent N` | Indentation width (default: 2) |
| `--colon-separator` | Use `:` instead of `=` in object elements |
| `--no-trailing-comma` | Omit trailing commas in object elements |
| `--heredocs-to-strings` | Convert heredocs to plain strings |
| `--strings-to-heredocs` | Convert strings with escaped newlines to heredocs |
| `--no-open-empty-blocks` | Collapse empty blocks to a single line |
| `--no-open-empty-objects` | Collapse empty objects to a single line |
| `--open-empty-tuples` | Expand empty tuples across multiple lines |
| `--no-align` | Disable vertical alignment of attributes and object elements |
| `--version` | Show version and exit |

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
