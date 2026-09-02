"""Out-of-band metadata for serialized bodies.

The serializer has three things to say about a body that are not attributes of
it: that it is a block, what comments surround it, and which of those were
inline. They have always travelled as `__is_block__`, `__comments__` and
`__inline_comments__` keys in the same dict as the attributes, which works only
while no document declares an attribute by those names. HCL puts no such name
out of reach, so one that does loses either the attribute or the metadata,
silently and in both directions.

`HclDict` carries them beside the mapping instead. It is a `dict`, so every
consumer that reads attributes keeps working unchanged, and `hcl_meta` holds
what used to sit among them.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HclMeta:
    """What the serializer knows about a body that is not one of its attributes."""

    is_block: bool = False
    comments: List[dict] = field(default_factory=list)
    inline_comments: List[dict] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Whether there is nothing here worth carrying."""
        return not (self.is_block or self.comments or self.inline_comments)


class HclDict(Dict[str, Any]):
    """A dict whose HCL metadata lives on the object rather than among the keys.

    Equality, iteration, `json.dumps` and every other mapping operation behave
    exactly as `dict` does -- the metadata is deliberately not part of the
    mapping, so a document declaring an attribute called `__is_block__` gets
    that attribute back and nothing else.

    JSON cannot carry the sidecar. Serializing an `HclDict` yields the
    attributes alone, which is why the in-band keys remain the default.
    """

    __slots__ = ("hcl_meta",)

    def __init__(self, *args: Any, meta: Optional[HclMeta] = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.hcl_meta = meta if meta is not None else HclMeta()

    def __repr__(self) -> str:
        """Show the metadata, so a debugging session does not have to guess."""
        if self.hcl_meta.is_empty():
            return super().__repr__()
        return f"{super().__repr__()} + {self.hcl_meta!r}"


def meta_of(value: Any) -> Optional[HclMeta]:
    """Return the metadata carried beside *value*, or None if it carries none."""
    meta = getattr(value, "hcl_meta", None)
    return meta if isinstance(meta, HclMeta) else None
