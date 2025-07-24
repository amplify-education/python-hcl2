import json
from typing import Any, TextIO, List

from hcl2.rule_transformer.rules.abstract import LarkElement, LarkRule
from hcl2.rule_transformer.utils import DeserializationOptions


class Deserializer:
    def __init__(self, options=DeserializationOptions()):
        self.options = options

    def load_python(self, value: Any) -> LarkElement:
        pass

    def loads(self, value: str) -> LarkElement:
        return self.load_python(json.loads(value))

    def load(self, file: TextIO) -> LarkElement:
        return self.loads(file.read())

    def _deserialize(self, value: Any) -> LarkElement:
        pass

    def _deserialize_dict(self, value: dict) -> LarkRule:
        pass

    def _deserialize_list(self, value: List) -> LarkRule:
        pass

    def _deserialize_expression(self, value: str) -> LarkRule:
        pass
