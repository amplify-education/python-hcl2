"""A utility class for constructing HCL documents from Python code."""
from typing import List, Optional

from collections import defaultdict

from hcl2.const import IS_BLOCK


class Builder:
    """
    The `hcl2.Builder` class produces a dictionary that should be identical to the
    output of `hcl2.load(example_file)`. HCL "blocks" in the Python dictionary are
    identified by the presence of `__is_block__: True` markers within them.
    The `Builder` class handles adding that marker. If that marker is missing,
    the deserializer fails to distinguish blocks from regular object attributes.
    """

    def __init__(self, attributes: Optional[dict] = None):
        self.blocks: dict = defaultdict(list)
        self.attributes = attributes or {}

    def block(
        self,
        block_type: str,
        labels: Optional[List[str]] = None,
        __nested_builder__: Optional["Builder"] = None,
        **attributes
    ) -> "Builder":
        """Create a block within this HCL document."""

        if __nested_builder__ is self:
            raise ValueError(
                "__nested__builder__ cannot be the same instance as instance this method is called on"
            )

        labels = labels or []
        block = Builder(attributes)

        # store the block in the document
        self.blocks[block_type].append((labels.copy(), block, __nested_builder__))

        return block

    def build(self):
        """Return the Python dictionary for this HCL document."""
        body = defaultdict(list)

        body.update(
            {
                IS_BLOCK: True,
                **self.attributes,
            }
        )

        for block_type, blocks in self.blocks.items():

            for labels, block_builder, nested_blocks in blocks:
                # build the sub-block
                block = block_builder.build()

                if nested_blocks:
                    self._add_nested_blocks(block, nested_blocks)

                # apply any labels
                for label in reversed(labels):
                    block = {label: block}

                # store it in the body
                body[block_type].append(block)

        return body

    def _add_nested_blocks(
        self, block: dict, nested_blocks_builder: "Builder"
    ) -> "dict":
        """Add nested blocks defined within another `Builder` instance to the `block` dictionary"""
        nested_block = nested_blocks_builder.build()
        for key, value in nested_block.items():
            if key != IS_BLOCK:
                if key not in block.keys():
                    block[key] = []
                block[key].extend(value)
        return block
