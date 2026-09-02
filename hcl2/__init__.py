"""For package documentation, see README"""

try:
    from .version import version as __version__
except ImportError:
    __version__ = "unknown"

from .api import (
    dump,
    dumps,
    from_dict,
    from_json,
    load,
    loads,
    parse,
    parse_to_tree,
    parses,
    parses_to_tree,
    query,
    reconstruct,
    serialize,
    transform,
)
from .builder import Builder
from .deserializer import DeserializerOptions
from .formatter import FormatterOptions
from .meta import HclDict, HclMeta, meta_of
from .rules.base import StartRule
from .utils import SerializationOptions

__all__ = [
    "Builder",
    "DeserializerOptions",
    "dump",
    "dumps",
    "FormatterOptions",
    "from_dict",
    "from_json",
    "HclDict",
    "HclMeta",
    "load",
    "loads",
    "meta_of",
    "parse",
    "parse_to_tree",
    "parses",
    "parses_to_tree",
    "query",
    "reconstruct",
    "SerializationOptions",
    "serialize",
    "StartRule",
    "transform",
]
