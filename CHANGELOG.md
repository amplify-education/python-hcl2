# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## \[2.0.0] - 2020-11-02

### Changed
-   Added support for Python 3.9
-   Upgraded to Lark parser 0.10

### Fixed
-   Fixed errors caused by identifiers named "true", "false", or "null"

## \[1.0.0] - 2020-09-30

### Changed
-   Treat one line blocks the same as multi line blocks.
    This is a breaking change so bumping to 1.0.0 to make sure no one accidentally upgrades to this version 
    without being aware of the breaking change. 
    Thank you @arielkru ([#35](https://github.com/amplify-education/python-hcl2/pull/35))

## \[0.3.2] - 2020-09-29

### Changed
-   Added support for colon separators in object definitions as specified in the [spec](https://github.com/hashicorp/hcl/blob/hcl2/hclsyntax/spec.md#collection-values) 

## \[0.3.1] - 2020-09-27

### Changed
-   Added support for legacy array index notation using dot. Thank you @arielkru ([#36](https://github.com/amplify-education/python-hcl2/pull/36))
