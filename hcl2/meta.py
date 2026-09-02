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

import copy as copy_module
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


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

    def __init__(self, *args: Any, meta: Optional[HclMeta] = None) -> None:
        """Build from a mapping, with the metadata passed separately.

        No `**kwargs`: this is the one class whose whole point is that no key
        name is reserved, and taking keyword items would reserve `meta` --
        `HclDict(**{"meta": "prod"})` would swallow the attribute and store a
        string where the metadata goes. `meta` is a real name in real configs.
        Pass the mapping positionally, as `dict` also allows.
        """
        super().__init__(*args)
        if meta is not None and not isinstance(meta, HclMeta):
            raise TypeError(
                "HclDict(meta=...) takes an HclMeta; to store a key called "
                f"'meta', pass the mapping positionally: HclDict({{'meta': {meta!r}}})"
            )
        self.hcl_meta = meta if meta is not None else HclMeta()

    def __repr__(self) -> str:
        """Show the metadata, so a debugging session does not have to guess."""
        if self.hcl_meta.is_empty():
            return super().__repr__()
        return f"{super().__repr__()} + {self.hcl_meta!r}"

    def copy(self) -> "HclDict":
        """Copy the mapping and the metadata together.

        `dict.copy` returns a plain `dict`, which would drop the sidecar --
        and `document = document.copy()` is ordinary enough that losing block
        metadata to it would be a trap. The in-band form survives a copy
        because its metadata is among the keys; this has to say so explicitly.
        """
        return HclDict(self, meta=copy_module.copy(self.hcl_meta))

    def __copy__(self) -> "HclDict":
        """Same for `copy.copy`."""
        return self.copy()

    def __deepcopy__(self, memo: dict) -> "HclDict":
        """Same for `copy.deepcopy`, metadata included."""
        duplicate = HclDict(
            {key: copy_module.deepcopy(value, memo) for key, value in self.items()},
            meta=copy_module.deepcopy(self.hcl_meta, memo),
        )
        memo[id(self)] = duplicate
        return duplicate

    def __reduce__(self) -> Tuple[Any, ...]:
        """Carry the metadata through pickling, which `dict` would not."""
        return (_rebuild, (dict(self), self.hcl_meta))

    def __or__(self, other: Any) -> "HclDict":  # type: ignore[override]
        """Merge, keeping this side's metadata.

        Narrower than `dict.__or__`, which is declared to return `dict` for any
        mapping: this always returns an `HclDict`, so the ignore records a
        deliberate narrowing rather than a mismatch.

        `dict.__or__` returns a plain `dict`, so `body | {"size": ...}` -- the
        idiomatic non-mutating edit -- would drop the sidecar and the block
        would then be written as an object. `{**body, ...}` cannot be helped:
        unpacking always builds a plain `dict`, and there is no hook for it.
        """
        merged = HclDict(self, meta=copy_module.copy(self.hcl_meta))
        merged.update(other)
        return merged

    def __ror__(self, other: Any) -> "HclDict":  # type: ignore[override]
        """Same from the left, keeping this side's metadata."""
        merged = HclDict(other, meta=copy_module.copy(self.hcl_meta))
        merged.update(self)
        return merged


def meta_of(value: Any) -> Optional[HclMeta]:
    """Return the metadata carried beside *value*, or None if it carries none."""
    meta = getattr(value, "hcl_meta", None)
    return meta if isinstance(meta, HclMeta) else None


def _rebuild(items: Dict[str, Any], meta: HclMeta) -> HclDict:
    """Reconstruct an `HclDict` from its pickled parts."""
    return HclDict(items, meta=meta)
