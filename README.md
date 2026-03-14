[![Codacy Badge](https://app.codacy.com/project/badge/Grade/2e2015f9297346cbaa788c46ab957827)](https://app.codacy.com/gh/amplify-education/python-hcl2/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://raw.githubusercontent.com/amplify-education/python-hcl2/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/python-hcl2.svg)](https://pypi.org/project/python-hcl2/)
[![Python Versions](https://img.shields.io/pypi/pyversions/python-hcl2.svg)](https://pypi.python.org/pypi/python-hcl2)
[![Downloads](https://img.shields.io/badge/dynamic/json.svg?label=downloads&url=https%3A%2F%2Fpypistats.org%2Fapi%2Fpackages%2Fpython-hcl2%2Frecent&query=data.last_month&colorB=brightgreen&suffix=%2FMonth)](https://pypistats.org/packages/python-hcl2)

# Python HCL2

A parser for [HCL2](https://github.com/hashicorp/hcl/blob/hcl2/hclsyntax/spec.md) written in Python using
[Lark](https://github.com/lark-parser/lark). This parser only supports HCL2 and isn't backwards compatible
with HCL v1. It can be used to parse any HCL2 config file such as Terraform.

## About Amplify

Amplify builds innovative and compelling digital educational products that empower teachers and students across the
country. We have a long history as the leading innovator in K-12 education - and have been described as the best tech
company in education and the best education company in tech. While others try to shrink the learning experience into
the technology, we use technology to expand what is possible in real classrooms with real students and teachers.

Learn more at <https://www.amplify.com>

## Getting Started

### Prerequisites

python-hcl2 requires Python 3.8 or higher to run.

### Installing

This package can be installed using `pip`

```sh
pip3 install python-hcl2
```

### Usage

**HCL2 to Python dict:**

```python
import hcl2

with open("main.tf") as f:
    data = hcl2.load(f)
```

**Python dict to HCL2:**

```python
import hcl2

hcl_string = hcl2.dumps(data)

with open("output.tf", "w") as f:
    hcl2.dump(data, f)
```

**Building HCL from scratch:**

```python
import hcl2

doc = hcl2.Builder()
res = doc.block("resource", labels=["aws_instance", "web"], ami="abc-123", instance_type="t2.micro")
res.block("tags", Name="HelloWorld")

hcl_string = hcl2.dumps(doc.build())
```

### Documentation

| Guide | Contents |
|---|---|
| [Getting Started](docs/01_getting_started.md) | Installation, load/dump, options, CLI converters |
| [Querying HCL (Python)](docs/02_querying.md) | DocumentView, BlockView, tree walking, view hierarchy |
| [Advanced API](docs/03_advanced_api.md) | Pipeline stages, Builder |
| [hq Reference](docs/04_hq.md) | `hq` CLI — structural queries, hybrid/eval, introspection |

### CLI Tools

python-hcl2 ships three command-line tools:

```sh
# HCL2 → JSON
hcl2tojson main.tf                     # prints JSON to stdout
hcl2tojson main.tf output.json         # writes to file
hcl2tojson terraform/ output/          # converts a directory

# JSON → HCL2
jsontohcl2 output.json                 # prints HCL2 to stdout
jsontohcl2 output.json main.tf         # writes to file
jsontohcl2 output/ terraform/          # converts a directory

# Query HCL2 files
hq 'resource.aws_instance.main.ami' main.tf
hq 'variable[*]' variables.tf --json
```

All commands accept `-` as PATH to read from stdin. Run `--help` on any command for the full list of flags.

## Building From Source

For development, `tox>=4.0.9` is recommended.

### Running Tests

python-hcl2 uses `tox`. You will need to install tox with `pip install tox`.
Running `tox` will automatically execute linters as well as the unit tests.

You can also run them individually with the `-e` argument.

For example, `tox -e py310-unit` will run the unit tests for python 3.10

To see all the available options, run `tox -l`.

## Releasing

To create a new release go to Releases page, press 'Draft a new release', create a tag
with a version you want to be released, fill the release notes and press 'Publish release'.
Github actions will take care of publishing it to PyPi.

## Responsible Disclosure

If you have any security issue to report, contact project maintainers privately.
You can reach us at <mailto:github@amplify.com>

## Contributing

We welcome pull requests! For your pull request to be accepted smoothly, we suggest that you:

- For any sizable change, first open a GitHub issue to discuss your idea.
- Create a pull request. Explain why you want to make the change and what it's for.

We'll try to answer any PR's promptly.

## Limitations

None that are known.
