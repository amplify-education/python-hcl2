"""The API that will be exposed to users of this package"""
from typing import TextIO

from lark.tree import Tree as AST
from hcl2.parser import hcl2
from hcl2.transformer import DictTransformer


def load(file: TextIO, with_meta=False) -> dict:
    """Load a HCL2 file.
    :param file: File with hcl2 to be loaded as a dict.
    :param with_meta: If set to true then adds `__start_line__` and `__end_line__`
    parameters to the output dict. Default to false.
    """
    return loads(file.read(), with_meta=with_meta)


def loads(text: str, with_meta=False) -> dict:
    """Load HCL2 from a string.
    :param text: Text with hcl2 to be loaded as a dict.
    :param with_meta: If set to true then adds `__start_line__` and `__end_line__`
    parameters to the output dict. Default to false.
    """
    # append new line as a workaround for https://github.com/lark-parser/lark/issues/237
    # Lark doesn't support a EOF token so our grammar can't look for "new line or end of file"
    # This means that all blocks must end in a new line even if the file ends
    # Append a new line as a temporary fix
    tree = hcl2.parse(text + "\n")
    return DictTransformer(with_meta=with_meta).transform(tree)


def parse(file: TextIO) -> AST:
    """Load HCL2 syntax tree from a file.
    :param file: File with hcl2 to be loaded as a dict.
    """
    return parses(file.read())


def parses(text: str) -> AST:
    """Load HCL2 syntax tree from a string.
    :param text: Text with hcl2 to be loaded as a dict.
    """
    # defer this import until this method is called, due to the performance hit
    # of rebuilding the grammar without cache
    from hcl2.reconstructor import (  # pylint: disable=import-outside-toplevel
        hcl2 as uncached_hcl2,
    )

    return uncached_hcl2.parse(text)


def transform(ast: AST, with_meta=False) -> dict:
    """Convert an HCL2 AST to a dictionary.
    :param ast: HCL2 syntax tree, output from `parse` or `parses`
    """
    return DictTransformer(with_meta=with_meta).transform(ast)


def reverse_transform(hcl2_dict: dict) -> AST:
    """Convert a dictionary to an HCL2 AST.
    :param dict: a dictionary produced by `load` or `transform`
    """
    # defer this import until this method is called, due to the performance hit
    # of rebuilding the grammar without cache
    from hcl2.reconstructor import (  # pylint: disable=import-outside-toplevel
        hcl2_reverse_transformer,
    )

    return hcl2_reverse_transformer.transform(hcl2_dict)


def writes(ast: AST) -> str:
    """Convert an HCL2 syntax tree to a string.
    :param ast: HCL2 syntax tree, output from `parse` or `parses`
    """
    # defer this import until this method is called, due to the performance hit
    # of rebuilding the grammar without cache
    from hcl2.reconstructor import (  # pylint: disable=import-outside-toplevel
        hcl2_reconstructor,
    )

    return hcl2_reconstructor.reconstruct(ast)
