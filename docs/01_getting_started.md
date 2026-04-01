# Getting Started

python-hcl2 parses [HCL2](https://github.com/hashicorp/hcl/blob/hcl2/hclsyntax/spec.md) into Python dicts and converts them back. This guide covers installation, everyday usage, and the CLI tools.

## Installation

python-hcl2 requires Python 3.8 or higher.

```sh
pip install python-hcl2
```

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
| `hcl2.query(source)` | Query HCL documents with typed view facades |

For intermediate pipeline stages (`parse_to_tree`, `transform`, `serialize`, `from_dict`, `from_json`, `reconstruct`) and the `Builder` class, see [Advanced API Reference](03_advanced_api.md).

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

The default serialization options are tuned for **content fidelity** — the output preserves enough detail (`__is_block__` markers, heredoc delimiters, quoted strings like `'"hello"'`, scientific notation, etc.) that it can be deserialized back into a LarkElement tree and reconstructed into valid HCL2 without information loss. This makes the defaults ideal for round-trip workflows (`load` → modify → `dump`), but it does add noise to the output compared to what you might expect from a plain JSON conversion. If you only need to *read* values and don't plan to reconstruct HCL2 from the dict, you can disable options like `explicit_blocks` and `preserve_heredocs`, or enable `strip_string_quotes` for cleaner output.

Pass `serialization_options` to control how the dict is produced:

```python
from hcl2 import loads, SerializationOptions

data = loads(text, serialization_options=SerializationOptions(
    with_meta=True,
    wrap_objects=True,
))
```

| Field | Type | Default | Description                                                                                                                                     |
|---|---|---|-------------------------------------------------------------------------------------------------------------------------------------------------|
| `with_comments` | `bool` | `True` | Include comments as `__comments__` and `__inline_comments__` keys (see [Comment Format](#comment-format))                                       |
| `with_meta` | `bool` | `False` | Add `__start_line__` / `__end_line__` metadata                                                                                                  |
| `wrap_objects` | `bool` | `False` | Wrap object values as inline HCL2 strings                                                                                                       |
| `wrap_tuples` | `bool` | `False` | Wrap tuple values as inline HCL2 strings                                                                                                        |
| `explicit_blocks` | `bool` | `True` | Add `__is_block__: True` markers to blocks. **Mandatory for JSON->HCL2 deserialization and reconstruction.**                                    |
| `preserve_heredocs` | `bool` | `True` | Keep heredocs in their original form                                                                                                            |
| `force_operation_parentheses` | `bool` | `False` | Force parentheses around all operations                                                                                                         |
| `preserve_scientific_notation` | `bool` | `True` | Keep scientific notation as-is                                                                                                                  |
| `strip_string_quotes` | `bool` | `False` | Remove surrounding quotes from string values (e.g. `"hello"` instead of `'"hello"'`). **Breaks JSON->HCL2 deserialization and reconstruction.** |

### Comment Format

When `with_comments` is enabled (the default), comments are included as lists of objects under the `__comments__` and `__inline_comments__` keys. Each object has a `"value"` key containing the comment text (with delimiters stripped):

```python
from hcl2 import loads, SerializationOptions

data = loads(
    "# Configure the provider\nx = 1\n",
    serialization_options=SerializationOptions(with_comments=True),
)

data["__comments__"]
# [{"value": "Configure the provider"}]
```

`__comments__` contains standalone comments (on their own lines), while `__inline_comments__` contains comments found inside expressions.

> **Note:** Comments are currently **read-only** — they are captured during parsing but not restored when converting a dict back to HCL2 with `dump`/`dumps`.

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

## CLI Tools

python-hcl2 ships three console scripts: `hcl2tojson`, `jsontohcl2`, and [`hq`](04_hq.md).

### hcl2tojson

Convert HCL2 files to JSON. Accepts files, directories, glob patterns, or stdin (default when no args given).

```sh
hcl2tojson main.tf                          # single file to stdout
hcl2tojson main.tf -o output.json           # single file to output file
hcl2tojson terraform/ -o output/            # directory to output dir
hcl2tojson terraform/                       # directory to stdout (NDJSON)
hcl2tojson --ndjson 'modules/**/*.tf'       # glob + NDJSON streaming
hcl2tojson a.tf b.tf -o output/             # multiple files to output dir
hcl2tojson --only resource,module main.tf   # block type filtering
hcl2tojson --fields cpu,memory main.tf      # field projection
hcl2tojson --compact main.tf                # single-line JSON
echo 'x = 1' | hcl2tojson                  # stdin (no args needed)
```

**Exit codes:** 0 = success, 1 = partial (some skipped), 2 = all unparsable, 4 = I/O error.

**Flags:**

| Flag | Description |
|---|---|
| `-o`, `--output` | Output path (file for single input, directory for multiple) |
| `-s` | Skip un-parsable files |
| `-q`, `--quiet` | Suppress progress output on stderr |
| `--ndjson` | One JSON object per line (newline-delimited JSON) |
| `--compact` | Compact JSON output (no indentation) |
| `--json-indent N` | JSON indentation width (default: 2 for TTY, compact otherwise) |
| `--only TYPES` | Comma-separated block types to include |
| `--exclude TYPES` | Comma-separated block types to exclude |
| `--fields FIELDS` | Comma-separated field names to keep |
| `--with-meta` | Add `__start_line__` / `__end_line__` metadata |
| `--with-comments` | Include comments as `__comments__` / `__inline_comments__` object lists |
| `--wrap-objects` | Wrap object values as inline HCL2 |
| `--wrap-tuples` | Wrap tuple values as inline HCL2 |
| `--no-explicit-blocks` | Disable `__is_block__` markers |
| `--no-preserve-heredocs` | Convert heredocs to plain strings |
| `--force-parens` | Force parentheses around all operations |
| `--no-preserve-scientific` | Convert scientific notation to standard floats |
| `--strip-string-quotes` | Strip surrounding double-quotes from string values (breaks round-trip) |
| `--version` | Show version and exit |

> **Note on `--strip-string-quotes`:** This removes the surrounding `"..."` from serialized string values (e.g. `"\"my-bucket\""` becomes `"my-bucket"`). Useful for read-only workflows but round-trip through `jsontohcl2` is **not supported** with this option, as the parser cannot distinguish bare strings from expressions.

### jsontohcl2

Convert JSON files to HCL2. Accepts files, directories, glob patterns, or stdin (default when no args given).

```sh
jsontohcl2 output.json                       # single file to stdout
jsontohcl2 output.json -o main.tf            # single file to output file
jsontohcl2 output/ -o terraform/             # directory conversion
jsontohcl2 --diff original.tf modified.json  # preview changes as unified diff
jsontohcl2 --dry-run file.json               # convert without writing
jsontohcl2 --fragment -                       # attribute snippets from stdin
echo '{"x": 1}' | jsontohcl2                 # stdin (no args needed)
```

**Exit codes:** 0 = success, 1 = JSON parse error, 2 = bad HCL structure, 4 = I/O error, 5 = differences found (`--diff`).

**Flags:**

| Flag | Description |
|---|---|
| `-o`, `--output` | Output path (file for single input, directory for multiple) |
| `-s` | Skip un-parsable files |
| `-q`, `--quiet` | Suppress progress output on stderr |
| `--diff ORIGINAL` | Show unified diff against ORIGINAL file (exit 0 = identical, 5 = differs) |
| `--dry-run` | Convert and print to stdout without writing files |
| `--fragment` | Treat input as attribute dict, not full HCL document |
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

### hq

Query HCL2 files by structure, with optional Python expressions.

```sh
hq 'resource.aws_instance.main.ami' main.tf
hq 'variable[*]' variables.tf --json
```

For the full guide, see [hq Reference](04_hq.md).

## Next Steps

- [Querying HCL (Python)](02_querying.md) — navigate documents with typed view facades
- [Advanced API Reference](03_advanced_api.md) — intermediate pipeline stages, Builder, pipeline diagram
- [hq Reference](04_hq.md) — query HCL files from the command line
- [hq Examples](05_hq_examples.md) — validated real-world queries by use case
