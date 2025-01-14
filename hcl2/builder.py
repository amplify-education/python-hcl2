"""A utility class for constructing HCL documents from Python code."""

from typing import List, Optional


class Builder:
    """
    The `hcl2.Builder` class produces a dictionary that should be identical to the
    output of `hcl2.load(example_file, with_meta=True)`. The `with_meta` keyword
    argument is important here. HCL "blocks" in the Python dictionary are
    identified by the presence of `__start_line__` and `__end_line__` metadata
    within them. The `Builder` class handles adding that metadata. If that metadata
    is missing, the `hcl2.reconstructor.HCLReverseTransformer` class fails to
    identify what is a block and what is just an attribute with an object value.
    """

    def __init__(self, attributes: Optional[dict] = None):
        self.blocks: dict = {}
        self.attributes = attributes or {}

    def block(
        self, block_type: str, labels: Optional[List[str]] = None, **attributes: dict
    ) -> "Builder":
        """Create a block within this HCL document."""
        labels = labels or []
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
