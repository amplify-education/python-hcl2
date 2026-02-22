"""For package documentation, see README"""

try:
    from .version import version as __version__
except ImportError:
    __version__ = "unknown"

from .api import (
    load,
    loads,
    dump,
    dumps,
    parse,
    parses,
    parse_to_tree,
    parses_to_tree,
    from_dict,
    from_json,
    reconstruct,
    transform,
    serialize,
)

from .builder import Builder
from .deserializer import DeserializerOptions
from .formatter import FormatterOptions
from .rules.base import StartRule
from .utils import SerializationOptions
