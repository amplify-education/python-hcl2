"""The API that will be exposed to users of this package.

Follows the json module convention: load/loads for reading, dump/dumps for writing.
Also exposes intermediate pipeline stages for advanced usage.
"""

import json as _json
from typing import TextIO, Optional

from lark.tree import Tree

from hcl2.deserializer import BaseDeserializer, DeserializerOptions
from hcl2.formatter import BaseFormatter, FormatterOptions
from hcl2.parser import parser as _get_parser
from hcl2.reconstructor import HCLReconstructor
from hcl2.rules.base import StartRule
from hcl2.transformer import RuleTransformer
from hcl2.utils import SerializationOptions


# ---------------------------------------------------------------------------
# Primary API: load / loads / dump / dumps
# ---------------------------------------------------------------------------


def load(
    file: TextIO,
    *,
    serialization_options: Optional[SerializationOptions] = None,
) -> dict:
    """Load a HCL2 file and return a Python dict.

    :param file: File with HCL2 content.
    :param serialization_options: Options controlling serialization behavior.
    """
    return loads(file.read(), serialization_options=serialization_options)


def loads(
    text: str,
    *,
    serialization_options: Optional[SerializationOptions] = None,
) -> dict:
    """Load HCL2 from a string and return a Python dict.

    :param text: HCL2 text.
    :param serialization_options: Options controlling serialization behavior.
    """
    tree = parses(text)
    return serialize(tree, serialization_options=serialization_options)


def dump(
    data: dict,
    file: TextIO,
    *,
    deserializer_options: Optional[DeserializerOptions] = None,
    formatter_options: Optional[FormatterOptions] = None,
) -> None:
    """Write a Python dict as HCL2 to a file.

    :param data: Python dict (as produced by :func:`load`).
    :param file: Writable text file.
    :param deserializer_options: Options controlling deserialization behavior.
    :param formatter_options: Options controlling formatting behavior.
    """
    file.write(
        dumps(
            data,
            deserializer_options=deserializer_options,
            formatter_options=formatter_options,
        )
    )


def dumps(
    data: dict,
    *,
    deserializer_options: Optional[DeserializerOptions] = None,
    formatter_options: Optional[FormatterOptions] = None,
) -> str:
    """Convert a Python dict to an HCL2 string.

    :param data: Python dict (as produced by :func:`load`).
    :param deserializer_options: Options controlling deserialization behavior.
    :param formatter_options: Options controlling formatting behavior.
    """
    tree = from_dict(
        data,
        deserializer_options=deserializer_options,
        formatter_options=formatter_options,
    )
    return reconstruct(tree)


# ---------------------------------------------------------------------------
# Parsing: HCL text -> LarkElement tree or raw Lark tree
# ---------------------------------------------------------------------------


def parse(file: TextIO, *, discard_comments: bool = False) -> StartRule:
    """Parse a HCL2 file into a LarkElement tree.

    :param file: File with HCL2 content.
    :param discard_comments: If True, discard comments during transformation.
    """
    return parses(file.read(), discard_comments=discard_comments)


def parses(text: str, *, discard_comments: bool = False) -> StartRule:
    """Parse a HCL2 string into a LarkElement tree.

    :param text: HCL2 text.
    :param discard_comments: If True, discard comments during transformation.
    """
    lark_tree = parses_to_tree(text)
    return transform(lark_tree, discard_comments=discard_comments)


def parse_to_tree(file: TextIO) -> Tree:
    """Parse a HCL2 file into a raw Lark parse tree.

    :param file: File with HCL2 content.
    """
    return parses_to_tree(file.read())


def parses_to_tree(text: str) -> Tree:
    """Parse a HCL2 string into a raw Lark parse tree.

    :param text: HCL2 text.
    """
    # Append newline as workaround for https://github.com/lark-parser/lark/issues/237
    # Lark doesn't support EOF token so our grammar can't look for "new line or end of file"
    return _get_parser().parse(text + "\n")


# ---------------------------------------------------------------------------
# Intermediate pipeline stages
# ---------------------------------------------------------------------------


def from_dict(
    data: dict,
    *,
    deserializer_options: Optional[DeserializerOptions] = None,
    formatter_options: Optional[FormatterOptions] = None,
    apply_format: bool = True,
) -> StartRule:
    """Convert a Python dict into a LarkElement tree.

    :param data: Python dict (as produced by :func:`load`).
    :param deserializer_options: Options controlling deserialization behavior.
    :param formatter_options: Options controlling formatting behavior.
    :param apply_format: If True (default), apply formatting to the tree.
    """
    deserializer = BaseDeserializer(deserializer_options)
    tree = deserializer.load_python(data)
    if apply_format:
        formatter = BaseFormatter(formatter_options)
        formatter.format_tree(tree)
    return tree


def from_json(
    text: str,
    *,
    deserializer_options: Optional[DeserializerOptions] = None,
    formatter_options: Optional[FormatterOptions] = None,
    apply_format: bool = True,
) -> StartRule:
    """Convert a JSON string into a LarkElement tree.

    :param text: JSON string.
    :param deserializer_options: Options controlling deserialization behavior.
    :param formatter_options: Options controlling formatting behavior.
    :param apply_format: If True (default), apply formatting to the tree.
    """
    data = _json.loads(text)
    return from_dict(
        data,
        deserializer_options=deserializer_options,
        formatter_options=formatter_options,
        apply_format=apply_format,
    )


def reconstruct(tree) -> str:
    """Convert a LarkElement tree (or raw Lark tree) to an HCL2 string.

    :param tree: A :class:`StartRule` (LarkElement tree) or :class:`lark.Tree`.
    """
    reconstructor = HCLReconstructor()
    if isinstance(tree, StartRule):
        tree = tree.to_lark()
    return reconstructor.reconstruct(tree)


def transform(lark_tree: Tree, *, discard_comments: bool = False) -> StartRule:
    """Transform a raw Lark parse tree into a LarkElement tree.

    :param lark_tree: Raw Lark tree from :func:`parse_to_tree` or :func:`parse_string_to_tree`.
    :param discard_comments: If True, discard comments during transformation.
    """
    return RuleTransformer(discard_new_line_or_comments=discard_comments).transform(
        lark_tree
    )


def serialize(
    tree: StartRule,
    *,
    serialization_options: Optional[SerializationOptions] = None,
) -> dict:
    """Serialize a LarkElement tree to a Python dict.

    :param tree: A :class:`StartRule` (LarkElement tree).
    :param serialization_options: Options controlling serialization behavior.
    """
    if serialization_options is not None:
        return tree.serialize(options=serialization_options)
    return tree.serialize()
