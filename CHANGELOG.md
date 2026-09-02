# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## \[Unreleased\]

### Fixed

- Flattened heredoc bodies match the values Terraform and OpenTofu evaluate the same source to. Three things differed, all checked against OpenTofu v1.12.5 rather than read off the spec: the newline terminating the last content line was dropped (`<<EOT\nline\nEOT` returned `'line'`, not `'line\n'`); `<<-` measured its indent in spaces alone, so a tab-indented body was not dedented at all; and a whitespace-only line was excluded from the measurement but trimmed anyway. This is not a regression — 7.2.1 returned the same values — so it changes long-standing behaviour rather than restoring anything.
- A carriage return in a flattened heredoc body is written as `\r` rather than left raw. `preserve_heredocs=False` returns quoted-string *source*, and a quoted string cannot hold a literal carriage return: OpenTofu rejects one with "No closing marker was found for the string". A heredoc read out of a CRLF file therefore flattened to source that would not parse again. The value form (`strip_string_quotes=True`) is unchanged and still hands back real carriage returns. `strings_to_heredocs` resolves `\r` when it writes a body, so the two halves stay each other's inverse: a heredoc interprets no escape, so a body carrying a backslash and an `r` would be those two characters rather than the carriage return the value held.
- A `<<-` heredoc whose closing marker is indented with something other than spaces or tabs no longer appends that indentation to the value. The dedent already measured whitespace rather than spaces, matching OpenTofu, but the marker's own indent was stripped as `[ \t]*`, so a body indented with a non-breaking space, a vertical tab, a form feed or an ideographic space came back with one of those characters on the end. Four such cases are now in the table that `bin/heredoc_ground_truth` re-derives from OpenTofu.
- `strings_to_heredocs` leaves a value carrying a lone carriage return quoted. A heredoc body is read literally, so it can hold a `\r` only where one ends a line: OpenTofu rejects `<<EOF\nx\ry\nEOF` with "No closing marker was found for the string", while the quoted `"x\ry\n"` it came from is valid. Such a value stays quoted, for the same reason one that does not end in a newline does.
- `strings_to_heredocs` picks a delimiter the body cannot close. It wrote `<<EOF` over every value, so a string holding a line reading `EOF` -- a log excerpt, a shell script, an embedded config, the payloads heredocs are for -- ended its own heredoc early and produced a file that no longer parsed. A numbered variant is used when the body occupies `EOF`, and ordinary values are written exactly as before. The lines that count as markers are Terraform's, which are looser than this grammar's: OpenTofu ends a heredoc on `EOF  ` while `HEREDOC_TEMPLATE` here requires the newline to follow the word. A CRLF body counts too -- it is split on `\n`, so its lines carry their own `\r`, and OpenTofu ends a heredoc on `EOF\r` as readily as on `EOF `. ([#330](https://github.com/amplify-education/python-hcl2/issues/330))
- `strings_to_heredocs` no longer adds a line to the body it writes. The value's own trailing newline is the one that precedes the closing marker, so a heredoc was being emitted one line longer than the string it came from. A value that does not end in a newline is now left as a quoted string, since no heredoc can express it. Flattening a document and restoring it now yields HCL that OpenTofu evaluates identically to the original; five of the eleven values in the round-trip fixture did not survive it before.

## \[8.1.3\] - 2026-08-26

Several fixes below change the values `loads()` returns for input that already
parsed without error in 8.1.x — negative integer literals, both
`strip_string_quotes` behaviours, and the two heredoc body fixes. The previous
result was a bug in each case, so this stays a patch release; re-check your
expectations if you built around the old values.

### Fixed

- Restore `py.typed` marker so type checkers recognize `hcl2` (and `cli`) as typed packages. ([#299](https://github.com/amplify-education/python-hcl2/pull/299))
- Parse heredocs with an empty body again. A marker immediately followed by its closing delimiter failed to match, and the lexer then ran on to a later delimiter, silently absorbing the attributes in between. Thanks, @livingstaccato ([#312](https://github.com/amplify-education/python-hcl2/pull/312))
- Negative integer literals load as numbers again instead of `${-N}` expression strings, matching negative floats and the pre-8.x behaviour. Thanks, @livingstaccato ([#311](https://github.com/amplify-education/python-hcl2/pull/311))
- `strip_string_quotes` no longer unquotes string literals nested inside expressions, which produced invalid HCL such as `${upper(x)}` from `upper("x")`. Thanks, @livingstaccato ([#313](https://github.com/amplify-education/python-hcl2/pull/313))
- `strip_string_quotes` now resolves escape sequences, so the values it yields match what the option documents. Escapes naming a codepoint outside the Unicode range, or a lone surrogate, are preserved verbatim rather than raising. Thanks, @livingstaccato ([#313](https://github.com/amplify-education/python-hcl2/pull/313))
- Parse files with CRLF (`\r\n`) line endings, including heredocs. A `\r` acting as part of a line ending is ignored, so a CRLF file reconstructs with LF endings; a `\r` that is content — inside a quoted string or a heredoc body — is preserved. Thanks, @agu2347 ([#317](https://github.com/amplify-education/python-hcl2/pull/317))
- Flattened heredoc bodies keep their trailing blank lines and trailing spaces instead of being right-stripped away, for both `<<MARKER` and `<<-MARKER`. The closing marker line's own indentation is still removed, and a blank line no longer cancels the `<<-` dedent. Thanks, @agu2347 ([#318](https://github.com/amplify-education/python-hcl2/pull/318))
- Parse heredocs whose delimiter is a single character, such as `<<E`. The spec defines the delimiter as an Identifier, which permits one character. ([#323](https://github.com/amplify-education/python-hcl2/pull/323))
- `preserve_heredocs=False` combined with `strip_string_quotes` now returns the heredoc body as a plain multi-line string instead of escaping every newline to a literal `\n`. The escaping is still applied to the quoted source form produced without `strip_string_quotes`. ([#324](https://github.com/amplify-education/python-hcl2/pull/324))

## \[8.1.2\] - 2026-04-10

### Fixed

- `true`, `false`, and `null` now serialize to native JSON types instead of strings. ([#293](https://github.com/amplify-education/python-hcl2/issues/293))

## \[8.1.1\] - 2026-04-07

### Added

- v7-to-v8 migration guide and absolute GitHub links in README docs table. ([#287](https://github.com/amplify-education/python-hcl2/pull/287))

## \[8.1.0\] - 2026-04-07

### Added

- Full architecture overhaul: bidirectional HCL2 ↔ JSON pipeline with typed rule classes. ([#203](https://github.com/amplify-education/python-hcl2/pull/203))
- `hq` read-only query CLI for HCL2 files ([#277](https://github.com/amplify-education/python-hcl2/pull/277))
- Agent-friendly conversion CLIs: `hcl2tojson` and `jsontohcl2` ([#274](https://github.com/amplify-education/python-hcl2/pull/274))
- Add template directives support (`%{if}`, `%{for}`) in quoted strings ([#276](https://github.com/amplify-education/python-hcl2/pull/276))
- Support loading comments ([#134](https://github.com/amplify-education/python-hcl2/issues/134))
- CLAUDE.md ([#260](https://github.com/amplify-education/python-hcl2/pull/260))

### Fixed

- Ternary with strings parse error ([#55](https://github.com/amplify-education/python-hcl2/issues/55))
- "No terminal matches '|' in the current parser context" when parsing multi-line conditional ([#142](https://github.com/amplify-education/python-hcl2/issues/142))
- reverse_transform not working with object-type variables ([#231](https://github.com/amplify-education/python-hcl2/issues/231))
- reverse_transform not handling nested functions ([#235](https://github.com/amplify-education/python-hcl2/issues/235))
- `writes` omits quotes around map keys with `/` ([#236](https://github.com/amplify-education/python-hcl2/issues/236))
- Operator precedence bug ([#248](https://github.com/amplify-education/python-hcl2/issues/248))
- Empty string dictionary keys can't be parsed twice ([#249](https://github.com/amplify-education/python-hcl2/issues/249))
- jsonencode not deserialized correctly ([#250](https://github.com/amplify-education/python-hcl2/issues/250))
- Literal string "string" incorrectly quoted ([#251](https://github.com/amplify-education/python-hcl2/issues/251))
- Interpolation literals added to locals/variables in maps ([#252](https://github.com/amplify-education/python-hcl2/issues/252))
- Object literal expression can't be serialized ([#253](https://github.com/amplify-education/python-hcl2/issues/253))
- Heredocs should interpret backslash literally ([#262](https://github.com/amplify-education/python-hcl2/issues/262))
- Parsing a multi-line multi-conditional expression causes exception — Unexpected token Token('QMARK', '?') ([#269](https://github.com/amplify-education/python-hcl2/issues/269))
- Parsing error for multiline binary operators ([#246](https://github.com/amplify-education/python-hcl2/pull/246))

### Changed

- Updated package metadata: development status, dropped Python 3.7 support. ([#263](https://github.com/amplify-education/python-hcl2/pull/263))

## \[7.3.1\] - 2025-07-24

### Fixed

- Updated pyproject.toml dependencies. Thanks, @kkorlyak ([#244](https://github.com/amplify-education/python-hcl2/pull/244))

## \[7.3.0\] - 2025-07-23

### Fixed

- Issue parsing interpolations and escaped interpolations in a single string. ([#239](https://github.com/amplify-education/python-hcl2/pull/239))

## \[7.2.1\] - 2025-05-16

### Fixed

- More robust escaping for special characters. Thanks, @eranor ([#224](https://github.com/amplify-education/python-hcl2/pull/224))
- Issue parsing interpolation string as an object key ([#232](https://github.com/amplify-education/python-hcl2/pull/232))

## \[7.2.0\] - 2025-04-24

### Added

- Possibility to parse deeply nested interpolations (formerly a Limitation), Thanks again, @weaversam8 ([#223](https://github.com/amplify-education/python-hcl2/pull/223))

### Fixed

- Issue parsing ellipsis in a separate line within `for` expression ([#221](https://github.com/amplify-education/python-hcl2/pull/221))
- Issue parsing inline expression as an object key; **see Limitations in README.md** ([#222](https://github.com/amplify-education/python-hcl2/pull/222))
- Preserve literals of e-notation floats in parsing and reconstruction. Thanks, @eranor ([#226](https://github.com/amplify-education/python-hcl2/pull/226))

## \[7.1.0\] - 2025-04-10

### Added

- `hcl2.builder.Builder` - nested blocks support ([#214](https://github.com/amplify-education/python-hcl2/pull/214))

### Fixed

- Issue parsing parenthesesed identifier (reference) as an object key ([#212](https://github.com/amplify-education/python-hcl2/pull/212))
- Issue discarding empty lists when transforming python dictionary into Lark Tree ([#216](https://github.com/amplify-education/python-hcl2/pull/216))

## \[7.0.1\] - 2025-03-31

### Fixed

- Issue parsing dot-accessed attribute as an object key ([#209](https://github.com/amplify-education/python-hcl2/pull/209))

## \[7.0.0\] - 2025-03-27

### Added

- `Limitations` section to README.md ([#200](https://github.com/amplify-education/python-hcl2/pull/200))

### Fixed

- Issue handling heredoc with delimiter within text itself ([#194](https://github.com/amplify-education/python-hcl2/pull/194))
- Various issues with parsing object elements ([#197](https://github.com/amplify-education/python-hcl2/pull/197))
- Dictionary -> hcl2 reconstruction of `null` values ([#198](https://github.com/amplify-education/python-hcl2/pull/198))
- Inaccurate parsing of `null` values in some cases ([#206](https://github.com/amplify-education/python-hcl2/pull/206))
- Missing parenthesis in arithemetic expressions ([#194](https://github.com/amplify-education/python-hcl2/pull/199))
- Noticeable overhead when loading hcl2.reconstructor module ([#202](https://github.com/amplify-education/python-hcl2/pull/202))
- Escaped string interpolation (e.g. `"$${aws:username}"`) parsing ([#200](https://github.com/amplify-education/python-hcl2/pull/200))

### Removed

- Support for parsing interpolations nested more than 2 times (known-issue) ([#200](https://github.com/amplify-education/python-hcl2/pull/200))

## \[6.1.1\] - 2025-02-13

### Fixed

- `DictTransformer.to_tf_inline` - handle float type. ([#188](https://github.com/amplify-education/python-hcl2/pull/188))

## \[6.1.0\] - 2025-01-24

### Fixed

- fix e-notation and negative numbers literals. ([#182](https://github.com/amplify-education/python-hcl2/pull/182))
- fix parsing of `null`.  ([#184](https://github.com/amplify-education/python-hcl2/pull/184))
- DictTransformer - do not wrap type literals into `${` and `}`. ([#186](https://github.com/amplify-education/python-hcl2/pull/186))

## \[6.0.0\] - 2025-01-15

### Added

- Support full reconstruction of HCL from Python structures. Thanks, @weaversam8, @Nfsaavedra ([#177](https://github.com/amplify-education/python-hcl2/pull/177))

## \[5.1.1\] - 2024-10-15

### Added

- fix `tree-to-hcl2-reconstruction.md` URL in README.md ([#175](https://github.com/amplify-education/python-hcl2/pull/175))

## \[5.1.0\] - 2024-10-15

### Added

- support python 3.13 ([#170](https://github.com/amplify-education/python-hcl2/pull/170))
- add section about Tree->HCL2 reconstruction to the README.md ([#174](https://github.com/amplify-education/python-hcl2/pull/174))

## \[5.0.0\] - 2024-10-07

### Added

- Support full reconstruction of HCL from parse tree. Thanks, @weaversam8 ([#169](https://github.com/amplify-education/python-hcl2/pull/169))

## \[4.3.5\] - 2024-08-06

### Added

- additional test coverage ([#165](https://github.com/amplify-education/python-hcl2/pull/165))
- fix: Add support for attributes named "in". Thanks, @elisiariocouto ([#164](https://github.com/amplify-education/python-hcl2/pull/164))
- fix: add "for" attribute identifier. Thanks, @zhcli ([#167](https://github.com/amplify-education/python-hcl2/pull/167))
- allow `if` and `for_each` keywords to be used as identifiers ([#168](https://github.com/amplify-education/python-hcl2/pull/168))

### Added

## \[4.3.4\] - 2024-06-12

### Added

- fix codacy badge ([#157](https://github.com/amplify-education/python-hcl2/pull/157))
- Fix MANIFEST.in and/or Python dependency filename(s) ([#161](https://github.com/amplify-education/python-hcl2/pull/161))
- adds support for provider functions. Thanks, @lkwg82 ([#162](https://github.com/amplify-education/python-hcl2/pull/162))

## \[4.3.3\] - 2024-03-27

### Added

- Support for Python 3.12 ([#153](https://github.com/amplify-education/python-hcl2/pull/153))

## \[4.3.2\] - 2023-05-24

### Added

- Support for the conditional inside the nested locals without parentheses ([#138](https://github.com/amplify-education/python-hcl2/pull/129))

## \[4.3.1\] - 2023-05-02

### Added

- Support for the braces in the next line. Thanks @rout39574 ([#129](https://github.com/amplify-education/python-hcl2/pull/129))
- Support for the ternary multi-line expression. Thanks @seksham ([#128](https://github.com/amplify-education/python-hcl2/pull/128))

## \[4.3.0\] - 2022-01-16

### Added

- Add tests for multiline comments inside a tuple ([#118](https://github.com/amplify-education/python-hcl2/pull/118))
- Add `__begin_line__` and `__end_line__` meta parameters ([#120](https://github.com/amplify-education/python-hcl2/pull/120))
- Add feature to parse comments in function args and list elems ([#119](https://github.com/amplify-education/python-hcl2/pull/119))

### Fixed

- Support empty heredoc and fix catastrophic backtracking issue ([#117](https://github.com/amplify-education/python-hcl2/pull/117))

### Changed

- Use Lark with its cache feature, instead of creating a standalone parser by @erezsh ([#53](https://github.com/amplify-education/python-hcl2/pull/53))
- Refactor tests ([#114](https://github.com/amplify-education/python-hcl2/pull/114))
- Remove pycodestyle, add black, add numerous pre-commit checks ([#115](https://github.com/amplify-education/python-hcl2/pull/115))

## \[4.2.0\] - 2022-12-28

### Added

- Added support of the `lark ≥1.0,<2`. Thanks @KOLANICH ([#100](https://github.com/amplify-education/python-hcl2/pull/100))

### Changed

- Dropped support of the `lark <1.0`.
- Added code improvements

## \[4.1.0\] - 2022-12-27

### Added

- Added support of python 3.11

### Changed

- Moved from setup.py to pyproject.toml. Thanks @KOLANICH ([#98](https://github.com/amplify-education/python-hcl2/pull/98))
- Updated the tox version in github actions to >=4.0.9,\<5.
- Dropped completely python 3.6.

## \[4.0.0\] - 2022-12-14

### Added

- Added PEP improvements
- Added support of python 3.10

### Changed

- Dropped support of python 3.6
- Setup tox-gh-actions
- Migrated from nose to nose2

## \[3.0.5\] - 2022-03-21

### Fixed

- Fixed parsing of for expressions when there is a new line before the colon

## \[3.0.4\] - 2022-02-22

### Added

- Handle nested interpolations. Thanks @arielkru and @matt-land ([#61](https://github.com/amplify-education/python-hcl2/pull/61))

## \[3.0.3\] - 2022-02-20

### Fixed

- Fixed nested splat statements. Thanks @josh-barker ([#80](https://github.com/amplify-education/python-hcl2/pull/80))

## \[3.0.2\] - 2022-02-20

### Fixed

- Fixed an issue of whitespace around for expressions. Thanks @ryanking and @matchaxnb ([#87](https://github.com/amplify-education/python-hcl2/pull/87))

## \[3.0.1\] - 2021-07-15

### Changed

- Included the generated parser in the distribution.

## \[3.0.0\] - 2021-07-14

### Changed

- BREAKING CHANGES: Attributes in blocks are no longer transformed into Python lists. Thanks @raymondbutcher ([#73](https://github.com/amplify-education/python-hcl2/pull/73))

## \[2.0.3\] - 2021-03-04

### Changed

- Skipped more exceptions for un-parsable files. Thanks @tanasegabriel ([#60](https://github.com/amplify-education/python-hcl2/pull/60))

## \[2.0.2\] - 2021-03-04

### Changed

- Allowed empty objects. Thanks @santoshankr ([#59](https://github.com/amplify-education/python-hcl2/pull/59))

## \[2.0.1\] - 2020-12-24

### Changed

- Allowed multiline conditional statements. Thanks @stpierre ([#51](https://github.com/amplify-education/python-hcl2/pull/51))

## \[2.0.0\] - 2020-11-02

### Changed

- Added support for Python 3.9
- Upgraded to Lark parser 0.10

### Fixed

- Fixed errors caused by identifiers named "true", "false", or "null"

## \[1.0.0\] - 2020-09-30

### Changed

- Treat one line blocks the same as multi line blocks.
  This is a breaking change so bumping to 1.0.0 to make sure no one accidentally upgrades to this version
  without being aware of the breaking change.
  Thank you @arielkru ([#35](https://github.com/amplify-education/python-hcl2/pull/35))

## \[0.3.2\] - 2020-09-29

### Changed

- Added support for colon separators in object definitions as specified in the [spec](https://github.com/hashicorp/hcl/blob/hcl2/hclsyntax/spec.md#collection-values)

## \[0.3.1\] - 2020-09-27

### Changed

- Added support for legacy array index notation using dot. Thank you @arielkru ([#36](https://github.com/amplify-education/python-hcl2/pull/36))
