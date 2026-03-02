# HCL2 Parser Development Guidelines

When working with this HCL2 parser codebase, follow these architectural principles and patterns.

## Core Architecture Rules

**ALWAYS** understand the bidirectional pipeline:

```
Forward:  HCL2 Text → Lark Parse Tree → LarkElement Tree → Python Dict/JSON
Reverse:  Python Dict/JSON → LarkElement Tree → Lark Tree → HCL2 Text
```

**NEVER** bypass the LarkElement intermediate representation. It provides type safety and enables bidirectional transformations.

**REMEMBER** that separation of concerns is key:

- Grammar definition (`hcl2.lark`) — syntax rules
- Transformer (`transformer.py`) — Lark parse tree → LarkElement tree
- Serialization (`rules/*.serialize()`) — LarkElement tree → Python dict
- Deserializer (`deserializer.py`) — Python dict → LarkElement tree
- Formatter (`formatter.py`) — whitespace alignment and spacing on LarkElement trees
- Reconstructor (`reconstructor.py`) — LarkElement tree → HCL2 text via Lark

### Public API Design

**FOLLOW** the `json` module convention in `api.py`:

- `load/loads` — HCL2 text → Python dict
- `dump/dumps` — Python dict → HCL2 text
- Intermediate stages for advanced usage: `parse/parses`, `parse_to_tree/parses_to_tree`, `transform`, `serialize`, `from_dict`, `from_json`, `reconstruct`
- All option parameters are keyword-only

## Design Pattern Guidelines

### Rule-Based Transformation Pattern

**FOLLOW** the one-to-one mapping: each Lark grammar rule corresponds to exactly one `LarkRule` class.

**ENSURE** every rule class:

- Mirrors lark grammar definition
- Inherits from appropriate base class (`LarkRule` or `LarkToken`)
- Implements `lark_name()` returning the grammar rule name
- Provides typed property accessors for child elements
- Handles its own serialization logic via `serialize()`
- Defines `_children` static field with appropriate type hinting

**LOCATE** transformation logic in `hcl2/transformer.py`

### Type Safety Requirements

**USE** abstract base classes from `hcl2/rules/abstract.py` to define contracts.

**PROVIDE** comprehensive type hints for all rule children structures.

**LEVERAGE** the generic token system in `hcl2/rules/tokens.py` for dynamic token creation with caching.

### Modular Organization Rules

**ORGANIZE** rules by domain responsibility:

- **Structural rules** → `rules/base.py`
- **Container rules** → `rules/containers.py`
- **Expression rules** → `rules/expressions.py`
- **Literal rules** → `rules/literal_rules.py`
- **String rules** → `rules/strings.py`
- **Function rules** → `rules/functions.py`
- **Indexing rules** → `rules/indexing.py`
- **For-expression rules** → `rules/for_expressions.py`
- **Metadata rules** → `rules/whitespace.py`

**NEVER** mix concerns across these domains.

### Serialization Strategy Guidelines

**IMPLEMENT** context-aware serialization using:

- `SerializationOptions` for configuration
- `SerializationContext` for state tracking
- Context managers for temporary state changes

**REFERENCE** implementation patterns in `hcl2/utils.py`

**ENSURE** each rule type follows its serialization strategy:

- Structural rules create nested dictionaries
- Container rules handle collections with optional wrapping
- Expression rules generate `${...}` interpolation when needed
- Literal rules convert to appropriate Python types

## Critical Implementation Rules

### Block vs Object Distinction

**ALWAYS** preserve the semantic difference between HCL2 blocks and data objects.

**USE** `__is_block__` markers to maintain semantic intent during round-trips.

**IMPLEMENT** block recognition logic in deserializer that can distinguish blocks from regular objects.

**HANDLE** multi-label blocks by implementing recursive label extraction algorithms.

### Bidirectional Requirements

**ENSURE** every serialization operation has a corresponding deserialization counterpart.

**TEST** round-trip integrity: Parse → Serialize → Deserialize → Serialize should produce identical results.

**REFERENCE** deserialization patterns in `hcl2/deserializer.py`

### String Interpolation Handling

**SUPPORT** nested expression evaluation within `${expression}` syntax.

**HANDLE** escape sequences and literal text segments properly.

**MAINTAIN** context awareness when generating interpolation strings.

## Extension Guidelines

### Adding New Language Constructs

**FOLLOW** this exact sequence:

1. Add grammar rules to `hcl2.lark`
1. Create rule classes following existing patterns
1. Add transformer methods to map grammar to rules
1. Implement serialization logic in rule classes
1. Update deserializer for round-trip support

### Rule Implementation Conventions

**ALWAYS** implement these methods/properties:

- `lark_name()` static method
- Property accessors for child elements
- `serialize()` method with context support
- Type hints for `_children` structure

**FOLLOW** naming conventions consistent with existing rules.

### Testing Requirements

**USE** `unittest.TestCase` as the test framework (not pytest).

**ORGANIZE** tests into two directories:

- `test/unit/` — granular tests that instantiate rule objects directly (no parsing)
  - `test/unit/rules/` — one file per rules module (e.g., `test_expressions.py` covers `hcl2/rules/expressions.py`)
  - `test/unit/test_api.py`, `test/unit/test_builder.py`, etc. — other module tests
- `test/integration/` — full-pipeline tests using golden files
  - `test_round_trip.py` — suite-based step tests (HCL→JSON, JSON→JSON, JSON→HCL, full round-trip) that iterate over all suites in `hcl2_original/`
  - `test_specialized.py` — feature-specific integration tests (operator precedence, Builder round-trip) with golden files in `specialized/`

**USE** concrete stubs when testing ABCs (e.g., `StubExpression(ExpressionRule)` for testing `_wrap_into_parentheses` logic without the parser).

**RUN** tests with: `python -m unittest discover -s test -p "test_*.py" -v`

## Code Quality Rules

### Type Safety Requirements

**PROVIDE** full type hints to enable static analysis.

**USE** proper inheritance hierarchies to catch errors at runtime.

**IMPLEMENT** property-based access to prevent structural errors.

### Performance Considerations

**LEVERAGE** cached token creation to prevent duplicate instantiation.

**IMPLEMENT** lazy evaluation for context-sensitive processing.

**OPTIMIZE** tree traversal using parent-child references.

### Maintainability Standards

**ENSURE** each rule has single responsibility for one grammar construct.

**FOLLOW** open/closed principle: extend via new rules, don't modify existing ones.

**MAINTAIN** clear import dependencies and type relationships.

## File Organization Standards

**KEEP** core abstractions in `rules/abstract.py`

**GROUP** domain-specific rules by functionality in separate files

**SEPARATE** utility functions into dedicated modules

**MAINTAIN** grammar definition independence from implementation

**STRUCTURE** test infrastructure to support incremental validation

## Common Pitfalls to Avoid

**DO NOT** create direct transformations from parse tree to Python dict - always use LarkElement intermediate representation.

**DO NOT** mix serialization concerns across rule types - each rule handles its own format.

**DO NOT** ignore context when generating expressions - interpolation behavior depends on nesting.

**DO NOT** forget to update both serialization and deserialization when adding new constructs.

**DO NOT** bypass the factory pattern for token creation - use the cached `StringToken` system.

## When Making Changes

**ALWAYS** run round-trip tests after any modifications.

**VERIFY** that new rules follow existing patterns and conventions.

**UPDATE** both transformer and deserializer when adding language features.

**MAINTAIN** type safety and proper inheritance relationships.

**DOCUMENT** any new patterns or conventions introduced.

This architecture enables robust HCL2 parsing with full round-trip fidelity while maintaining code quality and extensibility.

## Keeping This File Current

**PROACTIVELY** update this file when your work changes the architecture, file organization, module responsibilities, public API surface, or testing conventions described above. If you add, rename, move, or delete modules, rules files, test directories, or pipeline stages — reflect those changes here before finishing the task. Stale documentation is worse than no documentation.
