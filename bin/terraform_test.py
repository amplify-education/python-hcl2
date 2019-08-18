#!/usr/bin/env python
"""
This script recursively loads and parses all terraform files in a directory

Usage:
    terraform_test.py [PATH]

Options:
    PATH    The directory to check. Defaults to the TERRAFORM_CONFIG environment variable

"""
import os

from docopt import docopt

from hcl2.parser import hcl2
from hcl2.version import __version__

if __name__ == '__main__':
    arguments = docopt(__doc__, version=__version__)
    target_dir = arguments["PATH"] if arguments["PATH"] else os.environ['TERRAFORM_CONFIG']
    for current_dir, dirs, files in os.walk(target_dir):
        for file in files:
            if ".terraform" not in current_dir and file.endswith(".tf"):
                file_path = os.path.join(current_dir, file)

                with open(file_path, 'r') as file2:
                    print(file_path)
                    hcl2.parse(file2.read())
