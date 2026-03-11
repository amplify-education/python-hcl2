# HCL2 Parser — CLAUDE.md

## Pipeline

```
Forward:  HCL2 Text → [PostLexer] → Lark Parse Tree → LarkElement Tree → Python Dict/JSON
Reverse:  Python Dict/JSON → LarkElement Tree → Lark Tree → HCL2 Text
Direct:   HCL2 Text → [PostLexer] → Lark Parse Tree → LarkElement Tree → Lark Tree → HCL2 Text
```

The **Direct** pipeline (`parse_to_tree` → `transform` → `to_lark` → `reconstruct`) skips serialization to dict, so all IR nodes (including `NewLineOrCommentRule` nodes for whitespace/comments) directly influence the reconstructed output. Any information discarded before the IR is lost in this pipeline.

## Module Map

| Module | Role |
|---|---|
| `hcl2/hcl2.lark` | Lark grammar definition |
| `hcl2/api.py` | Public API (`load/loads/dump/dumps` + intermediate stages) |
| `hcl2/postlexer.py` | Token stream transforms between lexer and parser |
| `hcl2/parser.py` | Lark parser factory with caching |
| `hcl2/transformer.py` | Lark parse tree → LarkElement tree |
| `hcl2/deserializer.py` | Python dict → LarkElement tree |
| `hcl2/formatter.py` | Whitespace alignment and spacing on LarkElement trees |
| `hcl2/reconstructor.py` | LarkElement tree → HCL2 text via Lark |
| `hcl2/builder.py` | Programmatic HCL document construction |
| `hcl2/utils.py` | `SerializationOptions`, `SerializationContext`, string helpers |
| `hcl2/const.py` | Constants: `IS_BLOCK`, `COMMENTS_KEY`, `INLINE_COMMENTS_KEY` |
| `cli/helpers.py` | File/directory/stdin conversion helpers |
| `cli/hcl_to_json.py` | `hcl2tojson` entry point |
| `cli/json_to_hcl.py` | `jsontohcl2` entry point |

`hcl2/__main__.py` is a thin wrapper that imports `cli.hcl_to_json:main`.

### Rules (one class per grammar rule)

| File | Domain |
|---|---|
| `rules/abstract.py` | `LarkElement`, `LarkRule`, `LarkToken` base classes |
| `rules/tokens.py` | `StringToken` (cached factory), `StaticStringToken`, punctuation constants |
| `rules/base.py` | `StartRule`, `BodyRule`, `BlockRule`, `AttributeRule` |
| `rules/containers.py` | `TupleRule`, `ObjectRule`, `ObjectElemRule`, `ObjectElemKeyRule` |
| `rules/expressions.py` | `ExprTermRule`, `BinaryOpRule`, `UnaryOpRule`, `ConditionalRule` |
| `rules/literal_rules.py` | `IntLitRule`, `FloatLitRule`, `IdentifierRule`, `KeywordRule` |
| `rules/strings.py` | `StringRule`, `InterpolationRule`, `HeredocTemplateRule` |
| `rules/functions.py` | `FunctionCallRule`, `ArgumentsRule` |
| `rules/indexing.py` | `GetAttrRule`, `SqbIndexRule`, splat rules |
| `rules/for_expressions.py` | `ForTupleExprRule`, `ForObjectExprRule`, `ForIntroRule`, `ForCondRule` |
| `rules/whitespace.py` | `NewLineOrCommentRule`, `InlineCommentMixIn` |

## Public API (`api.py`)

Follows the `json` module convention. All option parameters are keyword-only.

- `load/loads` — HCL2 text → Python dict
- `dump/dumps` — Python dict → HCL2 text
- Intermediate stages: `parse/parses`, `parse_to_tree/parses_to_tree`, `transform`, `serialize`, `from_dict`, `from_json`, `reconstruct`

### Option Dataclasses

**`SerializationOptions`** (LarkElement → dict):
`with_comments`, `with_meta`, `wrap_objects`, `wrap_tuples`, `explicit_blocks`, `preserve_heredocs`, `force_operation_parentheses`, `preserve_scientific_notation`

**`DeserializerOptions`** (dict → LarkElement):
`heredocs_to_strings`, `strings_to_heredocs`, `object_elements_colon`, `object_elements_trailing_comma`

**`FormatterOptions`** (whitespace/alignment):
`indent_length`, `open_empty_blocks`, `open_empty_objects`, `open_empty_tuples`, `vertically_align_attributes`, `vertically_align_object_elements`

## CLI

Console scripts defined in `pyproject.toml`. Both accept one or more positional `PATH` arguments (files, directories, or `-` for stdin) and an optional `-o`/`--output` flag. Additional option flags map directly to the option dataclass fields above.

```
hcl2tojson file.tf                          # single file to stdout
hcl2tojson a.tf b.tf -o out/               # multiple files to output dir
hcl2tojson --json-indent 2 --with-meta file.tf
jsontohcl2 --indent 4 --no-align file.json
```

Add new options as `parser.add_argument()` calls in the relevant entry point module.

## PostLexer (`postlexer.py`)

Lark's `postlex` parameter accepts a single object with a `process(stream)` method that transforms the token stream between the lexer and LALR parser. The `PostLexer` class is designed for extensibility: each transformation is a private method that accepts and yields tokens, and `process()` chains them together.

Current passes:

- `_merge_newlines_into_operators`

To add a new pass: create a private method with the same `(self, stream) -> generator` signature, and add a `yield from` call in `process()`.

## Hard Rules

These are project-specific constraints that must not be violated:

1. **Always use the LarkElement IR.** Never transform directly from Lark parse tree to Python dict or vice versa.
1. **Block vs object distinction.** Use `__is_block__` markers (`const.IS_BLOCK`) to preserve semantic intent during round-trips. The deserializer must distinguish blocks from regular objects.
1. **Bidirectional completeness.** Every serialization path must have a corresponding deserialization path. Test round-trip integrity: Parse → Serialize → Deserialize → Serialize produces identical results.
1. **One grammar rule = one `LarkRule` class.** Each class implements `lark_name()`, typed property accessors, `serialize()`, and declares `_children_layout: Tuple[...]` (annotation only, no assignment) to document child structure.
1. **Token caching.** Use the `StringToken` factory in `rules/tokens.py` — never create token instances directly.
1. **Interpolation context.** `${...}` generation depends on nesting depth — always pass and respect `SerializationContext`.
1. **Update both directions.** When adding language features, update transformer.py, deserializer.py, formatter.py and reconstructor.py.

## Adding a New Language Construct

1. Add grammar rules to `hcl2.lark`
1. If the new construct creates LALR ambiguities with `NL_OR_COMMENT`, add a postlexer pass in `postlexer.py`
1. Create rule class(es) in the appropriate `rules/` file
1. Add transformer method(s) in `transformer.py`
1. Implement `serialize()` in the rule class
1. Update `deserializer.py`, `formatter.py` and `reconstructor.py` for round-trip support

## Testing

Framework: `unittest.TestCase` (not pytest).

```
python -m unittest discover -s test -p "test_*.py" -v
```

**Unit tests** (`test/unit/`): instantiate rule objects directly (no parsing).

- `rules/` — one file per rules module
- `cli/` — one file per CLI module
- `test_*.py` — tests for corresponding files from `hcl2/` directory

Use concrete stubs when testing ABCs (e.g., `StubExpression(ExpressionRule)`).

**Integration tests** (`test/integration/`): full-pipeline tests with golden files.

- `test_round_trip.py` — iterates over all suites in `hcl2_original/`, tests HCL→JSON, JSON→JSON, JSON→HCL, and full round-trip
- `test_specialized.py` — feature-specific tests with golden files in `specialized/`

Always run round-trip full test suite after any modification.

## Pre-commit Checks

Hooks are defined in `.pre-commit-config.yaml` (includes black, mypy, pylint, and others). All changed files must pass these checks before committing. When writing or modifying code:

- Format Python with **black** (Python 3.8 target).
- Ensure **mypy** and **pylint** pass. Pylint config is in `pylintrc`, scoped to `hcl2/` and `test/`.
- End files with a newline; strip trailing whitespace (except under `test/integration/(hcl2_reconstructed|specialized)/`).

## Keeping Docs Current

Update this file when architecture, modules, API surface, or testing conventions change. Also update `README.md` and `docs/usage.md` when changes affect the public API, CLI flags, or option fields.
