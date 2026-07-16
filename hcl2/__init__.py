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
from .rules.base import StartRule
from .utils import SerializationOptions

__all__ = [
    "dump",
    "dumps",
    "from_dict",
    "from_json",
    "load",
    "loads",
    "parse",
    "parse_to_tree",
    "parses",
    "parses_to_tree",
    "query",
    "reconstruct",
    "serialize",
    "transform",
    "Builder",
    "DeserializerOptions",
    "FormatterOptions",
    "StartRule",
    "SerializationOptions",
]
