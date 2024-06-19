# pylint:disable=C0114,C0115,C0116

from lark import Tree

from hcl2.parser import hcl2
from hcl2.transformer import DictTransformer


class Hcl2Helper:
    @classmethod
    def load(cls, syntax: str) -> Tree:
        return hcl2.parse(syntax)

    @classmethod
    def load_to_dict(cls, syntax) -> dict:
        tree = cls.load(syntax)
        return DictTransformer().transform(tree)

    @classmethod
    def build_argument(cls, identifier: str, expression: str = '"expression"') -> str:
        return f"{identifier} = {expression}"
