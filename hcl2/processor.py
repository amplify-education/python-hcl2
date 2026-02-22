from copy import copy, deepcopy
from typing import (
    List,
    Optional,
    Union,
    Callable,
    Any,
    Tuple,
    Generic,
    TypeVar,
    cast,
    Generator,
)

from hcl2.rule_transformer.rules.abstract import LarkRule, LarkElement
from hcl2.rule_transformer.rules.base import BlockRule, AttributeRule
from hcl2.rule_transformer.rules.whitespace import NewLineOrCommentRule

T = TypeVar("T", bound=LarkRule)


class RulesProcessor(Generic[T]):
    """"""

    @classmethod
    def _traverse(
        cls,
        node: T,
        predicate: Callable[[T], bool],
        current_depth: int = 0,
        max_depth: Optional[int] = None,
    ) -> List["RulesProcessor"]:

        results = []

        if predicate(node):
            results.append(cls(node))

        if max_depth is not None and current_depth >= max_depth:
            return results

        for child in node.children:
            if child is None or not isinstance(child, LarkRule):
                continue

            child_results = cls._traverse(
                child,
                predicate,
                current_depth + 1,
                max_depth,
            )
            results.extend(child_results)

        return results

    def __init__(self, node: LarkRule):
        self.node = node

    @property
    def siblings(self):
        if self.node.parent is None:
            return None
        return self.node.parent.children

    @property
    def next_siblings(self):
        if self.node.parent is None:
            return None
        return self.node.parent.children[self.node.index + 1 :]

    @property
    def previous_siblings(self):
        if self.node.parent is None:
            return None
        return self.node.parent.children[: self.node.index - 1]

    def walk(self) -> Generator[Tuple["RulesProcessor", List["RulesProcessor"]]]:
        child_processors = [self.__class__(child) for child in self.node.children]
        yield self, child_processors
        for processor in child_processors:
            if isinstance(processor.node, LarkRule):
                for result in processor.walk():
                    yield result

    def find_block(
        self,
        labels: List[str],
        exact_match: bool = True,
        max_depth: Optional[int] = None,
    ) -> "RulesProcessor[BlockRule]":
        return self.find_blocks(labels, exact_match, max_depth)[0]

    def find_blocks(
        self,
        labels: List[str],
        exact_match: bool = True,
        max_depth: Optional[int] = None,
    ) -> List["RulesProcessor[BlockRule]"]:
        """
        Find blocks by their labels.

        Args:
            labels: List of label strings to match
            exact_match: If True, all labels must match exactly. If False, labels can be a subset.
            max_depth: Maximum depth to search

        Returns:
            ...
        """

        def block_predicate(node: LarkRule) -> bool:
            if not isinstance(node, BlockRule):
                return False

            node_labels = [label.serialize() for label in node.labels]

            if exact_match:
                return node_labels == labels
            else:
                # Check if labels is a prefix of node_labels
                if len(labels) > len(node_labels):
                    return False
                return node_labels[: len(labels)] == labels

        return cast(
            List[RulesProcessor[BlockRule]],
            self._traverse(self.node, block_predicate, max_depth=max_depth),
        )

    def attribute(
        self, name: str, max_depth: Optional[int] = None
    ) -> "RulesProcessor[AttributeRule]":
        return self.find_attributes(name, max_depth)[0]

    def find_attributes(
        self, name: str, max_depth: Optional[int] = None
    ) -> List["RulesProcessor[AttributeRule]"]:
        """
        Find attributes by their identifier name.

        Args:
            name: Attribute name to search for
            max_depth: Maximum depth to search

        Returns:
            List of TreePath objects for matching attributes
        """

        def attribute_predicate(node: LarkRule) -> bool:
            if not isinstance(node, AttributeRule):
                return False
            return node.identifier.serialize() == name

        return self._traverse(self.node, attribute_predicate, max_depth=max_depth)

    def rule(self, rule_name: str, max_depth: Optional[int] = None):
        return self.find_rules(rule_name, max_depth)[0]

    def find_rules(
        self, rule_name: str, max_depth: Optional[int] = None
    ) -> List["RulesProcessor"]:
        """
        Find all rules of a specific type.

        Args:
            rule_name: Name of the rule type to find
            max_depth: Maximum depth to search

        Returns:
            List of TreePath objects for matching rules
        """

        def rule_predicate(node: LarkRule) -> bool:
            return node.lark_name() == rule_name

        return self._traverse(self.node, rule_predicate, max_depth=max_depth)

    def find_by_predicate(
        self, predicate: Callable[[LarkRule], bool], max_depth: Optional[int] = None
    ) -> List["RulesProcessor"]:
        """
        Find all rules matching a custom predicate.

        Args:
            predicate: Function that returns True for nodes to collect
            max_depth: Maximum depth to search

        Returns:
            List of TreePath objects for matching rules
        """
        return self._traverse(self.node, predicate, max_depth)

    # Convenience methods
    def get_all_blocks(self, max_depth: Optional[int] = None) -> List:
        """Get all blocks in the tree."""
        return self.find_rules("block", max_depth)

    def get_all_attributes(
        self, max_depth: Optional[int] = None
    ) -> List["RulesProcessor"]:
        """Get all attributes in the tree."""
        return self.find_rules("attribute", max_depth)

    def previous(self, skip_new_line: bool = True) -> Optional["RulesProcessor"]:
        """Get the next sibling node."""
        if self.node.parent is None:
            return None

        for sibling in reversed(self.previous_siblings):
            if sibling is not None and isinstance(sibling, LarkRule):
                if skip_new_line and isinstance(sibling, NewLineOrCommentRule):
                    continue
                return self.__class__(sibling)

    def next(self, skip_new_line: bool = True) -> Optional["RulesProcessor"]:
        """Get the next sibling node."""
        if self.node.parent is None:
            return None

        for sibling in self.next_siblings:
            if sibling is not None and isinstance(sibling, LarkRule):
                if skip_new_line and isinstance(sibling, NewLineOrCommentRule):
                    continue
                return self.__class__(sibling)

    def append_child(
        self, new_node: LarkRule, indentation: bool = True
    ) -> "RulesProcessor":
        children = self.node.children
        if indentation:
            if isinstance(children[-1], NewLineOrCommentRule):
                children.pop()
            children.append(NewLineOrCommentRule.from_string("\n  "))

        new_node = deepcopy(new_node)
        new_node.set_parent(self.node)
        new_node.set_index(len(children))
        children.append(new_node)
        return self.__class__(new_node)

    def replace(self, new_node: LarkRule) -> "RulesProcessor":
        new_node = deepcopy(new_node)

        self.node.parent.children.pop(self.node.index)
        self.node.parent.children.insert(self.node.index, new_node)
        new_node.set_parent(self.node.parent)
        new_node.set_index(self.node.index)
        return self.__class__(new_node)

    # def insert_before(self, new_node: LarkRule) -> bool:
    #     """Insert a new node before this one."""
    #     if self.parent is None or self.parent_index < 0:
    #         return False
    #
    #     try:
    #         self.parent.children.insert(self.parent_index, new_node)
    #     except (IndexError, AttributeError):
    #         return False
