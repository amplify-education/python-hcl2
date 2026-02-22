import dataclasses
from copy import copy, deepcopy
from typing import List, Optional, Set, Tuple

from hcl2.rule_transformer.rules.abstract import LarkRule
from hcl2.rule_transformer.rules.base import BlockRule, StartRule


@dataclasses.dataclass
class TreePathElement:

    name: str
    index: int = 0


@dataclasses.dataclass
class TreePath:

    elements: List[TreePathElement] = dataclasses.field(default_factory=list)

    @classmethod
    def build(cls, elements: List[Tuple[str, Optional[int]] | str]):
        results = []
        for element in elements:
            if isinstance(element, tuple):
                if len(element) == 1:
                    result = TreePathElement(element[0], 0)
                else:
                    result = TreePathElement(*element)
            else:
                result = TreePathElement(element, 0)

            results.append(result)

        return cls(results)

    def __iter__(self):
        return self.elements.__iter__()

    def __len__(self):
        return self.elements.__len__()


class Editor:
    def __init__(self, rules_tree: LarkRule):
        self.rules_tree = rules_tree

    @classmethod
    def _find_one(cls, rules_tree: LarkRule, path_element: TreePathElement) -> LarkRule:
        return cls._find_all(rules_tree, path_element.name)[path_element.index]

    @classmethod
    def _find_all(cls, rules_tree: LarkRule, rule_name: str) -> List[LarkRule]:
        children = []
        print("rule", rules_tree)
        print("rule children", rules_tree.children)
        for child in rules_tree.children:
            if isinstance(child, LarkRule) and child.lark_name() == rule_name:
                children.append(child)

        return children

    def find_by_path(self, path: TreePath, rule_name: str) -> List[LarkRule]:
        path = deepcopy(path.elements)

        current_rule = self.rules_tree
        while len(path) > 0:
            current_path, *path = path
            print(current_path, path)
            current_rule = self._find_one(current_rule, current_path)

        return self._find_all(current_rule, rule_name)

    # def visit(self, path: TreePath) -> "Editor":
    #
    #     while len(path) > 1:
    #         current =
