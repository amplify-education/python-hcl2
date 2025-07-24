from json import JSONEncoder
from typing import Any

from hcl2.rule_transformer.rules.abstract import LarkRule


class LarkEncoder(JSONEncoder):
    def default(self, obj: Any):
        if isinstance(obj, LarkRule):
            return obj.serialize()
        else:
            return super().default(obj)
