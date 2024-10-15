# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

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
