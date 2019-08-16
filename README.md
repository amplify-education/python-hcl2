# python_hcl2
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://raw.githubusercontent.com/amplify-education/python_hcl2/master/LICENSE)

A project for being awesome.
# About Amplify
Amplify builds innovative and compelling digital educational products that empower teachers and students across the country. We have a long history as the leading innovator in K-12 education - and have been described as the best tech company in education and the best education company in tech. While others try to shrink the learning experience into the technology, we use technology to expand what is possible in real classrooms with real students and teachers.

Learn more at https://www.amplify.com

# Getting Started
## Prerequisites
python_hcl2 requires the following to be installed:
```
python >= 3.6
```

For development, `tox>=2.9.1` is recommended.

## Installing/Building
python_hcl2 is setup through tox, so simply run `tox`.

## Running Tests
As mentioned above, python_hcl2 uses tox, so running `tox` will automatically execute linters as well as the unit tests. You can also run functional and integration tests by using the -e argument.

For example, `tox -e lint,py27-unit,py27-integration` will run the linters, and then the unit and integration tests in python 2.7.

To see all the available options, run `tox -l`.

## Deployment
So how do we deploy this thing?

## Configuration
So how do we configure this thing?
# Responsible Disclosure
If you have any security issue to report, contact project maintainers privately.
You can reach us at <github@amplify.com>

# Contributing
We welcome pull requests! For your pull request to be accepted smoothly, we suggest that you:
1. For any sizable change, first open a GitHub issue to discuss your idea.
2. Create a pull request.  Explain why you want to make the change and what it’s for.
We’ll try to answer any PR’s promptly.
