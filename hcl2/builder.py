"""A utility class for constructing HCL documents from Python code."""

from typing import List
from typing_extensions import Self


class Builder:
    def __init__(self, attributes: dict = {}):
        self.blocks = {}
        self.attributes = attributes

    def block(
        self, block_type: str, labels: List[str] = [], **attributes: dict
    ) -> Self:
        """Create a block within this HCL document."""
        block = Builder(attributes)

        # initialize a holder for blocks of that type
        if block_type not in self.blocks:
            self.blocks[block_type] = []

        # store the block in the document
        self.blocks[block_type].append((labels.copy(), block))

        return block

    def build(self):
        """Return the Python dictionary for this HCL document."""
        body = {
            "__start_line__": -1,
            "__end_line__": -1,
            **self.attributes,
        }

        for block_type, blocks in self.blocks.items():

            # initialize a holder for blocks of that type
            if block_type not in body:
                body[block_type] = []

            for labels, block_builder in blocks:
                # build the sub-block
                block = block_builder.build()

                # apply any labels
                labels.reverse()
                for label in labels:
                    block = {label: block}

                # store it in the body
                body[block_type].append(block)

        return body
