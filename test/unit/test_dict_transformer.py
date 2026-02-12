# pylint:disable=C0114,C0116,C0103,W0612

from unittest import TestCase

from hcl2.dict_transformer import DictTransformer


class TestDictTransformer(TestCase):
    """Test behaviour of hcl2.transformer.DictTransformer class"""

    @staticmethod
    def build_dict_transformer(with_meta: bool = False) -> DictTransformer:
        return DictTransformer(with_meta)

    def test_to_string_dollar(self):
        string_values = {
            '"bool"': "bool",
            '"number"': "number",
            '"string"': "string",
            "${value_1}": "${value_1}",
            '"value_2': '${"value_2}',
            'value_3"': '${value_3"}',
            '"value_4"': "value_4",
            "value_5": "${value_5}",
        }

        dict_transformer = self.build_dict_transformer()

        for value, expected in string_values.items():
            actual = dict_transformer.to_string_dollar(value)

            self.assertEqual(actual, expected)
