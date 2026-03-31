"""Unit tests for template directive rule classes."""

# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.rules.directives import (
    TemplateIfStartRule,
    TemplateElseRule,
    TemplateEndifRule,
    TemplateForStartRule,
    TemplateEndforRule,
    TemplateIfRule,
    TemplateForRule,
)
from hcl2.rules.literal_rules import IdentifierRule
from hcl2.rules.strings import StringPartRule
from hcl2.rules.tokens import (
    NAME,
    DIRECTIVE_START,
    STRIP_MARKER,
    RBRACE,
    IF,
    ELSE,
    ENDIF,
    FOR,
    IN,
    ENDFOR,
    COMMA,
    STRING_CHARS,
)


class TestTemplateIfStartRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TemplateIfStartRule.lark_name(), "template_if_start")

    def test_serialize_basic(self):
        cond = IdentifierRule([NAME("cond")])
        rule = TemplateIfStartRule([DIRECTIVE_START(), IF(), cond, RBRACE()])
        self.assertEqual(rule.serialize(), "%{ if cond }")

    def test_serialize_strip_markers(self):
        cond = IdentifierRule([NAME("cond")])
        rule = TemplateIfStartRule(
            [DIRECTIVE_START(), STRIP_MARKER(), IF(), cond, STRIP_MARKER(), RBRACE()]
        )
        self.assertEqual(rule.serialize(), "%{~ if cond ~}")

    def test_condition_property(self):
        cond = IdentifierRule([NAME("x")])
        rule = TemplateIfStartRule([DIRECTIVE_START(), IF(), cond, RBRACE()])
        self.assertIs(rule.condition, cond)


class TestTemplateElseRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TemplateElseRule.lark_name(), "template_else")

    def test_serialize_basic(self):
        rule = TemplateElseRule([DIRECTIVE_START(), ELSE(), RBRACE()])
        self.assertEqual(rule.serialize(), "%{ else }")

    def test_serialize_strip_markers(self):
        rule = TemplateElseRule(
            [DIRECTIVE_START(), STRIP_MARKER(), ELSE(), STRIP_MARKER(), RBRACE()]
        )
        self.assertEqual(rule.serialize(), "%{~ else ~}")


class TestTemplateEndifRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TemplateEndifRule.lark_name(), "template_endif")

    def test_serialize_basic(self):
        rule = TemplateEndifRule([DIRECTIVE_START(), ENDIF(), RBRACE()])
        self.assertEqual(rule.serialize(), "%{ endif }")


class TestTemplateForStartRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TemplateForStartRule.lark_name(), "template_for_start")

    def test_serialize_basic(self):
        iterator = IdentifierRule([NAME("item")])
        collection = IdentifierRule([NAME("items")])
        rule = TemplateForStartRule(
            [DIRECTIVE_START(), FOR(), iterator, IN(), collection, RBRACE()]
        )
        self.assertEqual(rule.serialize(), "%{ for item in items }")

    def test_serialize_key_value(self):
        key = IdentifierRule([NAME("k")])
        val = IdentifierRule([NAME("v")])
        collection = IdentifierRule([NAME("map")])
        rule = TemplateForStartRule(
            [DIRECTIVE_START(), FOR(), key, COMMA(), val, IN(), collection, RBRACE()]
        )
        self.assertEqual(rule.serialize(), "%{ for k, v in map }")

    def test_serialize_strip_markers(self):
        iterator = IdentifierRule([NAME("x")])
        collection = IdentifierRule([NAME("xs")])
        rule = TemplateForStartRule(
            [
                DIRECTIVE_START(),
                STRIP_MARKER(),
                FOR(),
                iterator,
                IN(),
                collection,
                STRIP_MARKER(),
                RBRACE(),
            ]
        )
        self.assertEqual(rule.serialize(), "%{~ for x in xs ~}")


class TestTemplateEndforRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TemplateEndforRule.lark_name(), "template_endfor")

    def test_serialize_basic(self):
        rule = TemplateEndforRule([DIRECTIVE_START(), ENDFOR(), RBRACE()])
        self.assertEqual(rule.serialize(), "%{ endfor }")


class TestTemplateIfRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TemplateIfRule.lark_name(), "template_if")

    def test_serialize_basic(self):
        cond = IdentifierRule([NAME("cond")])
        if_start = TemplateIfStartRule([DIRECTIVE_START(), IF(), cond, RBRACE()])
        body = [StringPartRule([STRING_CHARS("yes")])]
        endif = TemplateEndifRule([DIRECTIVE_START(), ENDIF(), RBRACE()])
        rule = TemplateIfRule(if_start, body, None, None, endif)
        self.assertEqual(rule.serialize(), "%{ if cond }yes%{ endif }")

    def test_serialize_with_else(self):
        cond = IdentifierRule([NAME("cond")])
        if_start = TemplateIfStartRule([DIRECTIVE_START(), IF(), cond, RBRACE()])
        if_body = [StringPartRule([STRING_CHARS("yes")])]
        else_rule = TemplateElseRule([DIRECTIVE_START(), ELSE(), RBRACE()])
        else_body = [StringPartRule([STRING_CHARS("no")])]
        endif = TemplateEndifRule([DIRECTIVE_START(), ENDIF(), RBRACE()])
        rule = TemplateIfRule(if_start, if_body, else_rule, else_body, endif)
        self.assertEqual(rule.serialize(), "%{ if cond }yes%{ else }no%{ endif }")

    def test_serialize_strip_markers(self):
        cond = IdentifierRule([NAME("c")])
        if_start = TemplateIfStartRule(
            [DIRECTIVE_START(), STRIP_MARKER(), IF(), cond, STRIP_MARKER(), RBRACE()]
        )
        body = [StringPartRule([STRING_CHARS("x")])]
        endif = TemplateEndifRule(
            [DIRECTIVE_START(), STRIP_MARKER(), ENDIF(), STRIP_MARKER(), RBRACE()]
        )
        rule = TemplateIfRule(if_start, body, None, None, endif)
        self.assertEqual(rule.serialize(), "%{~ if c ~}x%{~ endif ~}")


class TestTemplateForRule(TestCase):
    def test_lark_name(self):
        self.assertEqual(TemplateForRule.lark_name(), "template_for")

    def test_serialize_basic(self):
        iterator = IdentifierRule([NAME("item")])
        collection = IdentifierRule([NAME("items")])
        for_start = TemplateForStartRule(
            [DIRECTIVE_START(), FOR(), iterator, IN(), collection, RBRACE()]
        )
        body = [StringPartRule([STRING_CHARS("text")])]
        endfor = TemplateEndforRule([DIRECTIVE_START(), ENDFOR(), RBRACE()])
        rule = TemplateForRule(for_start, body, endfor)
        self.assertEqual(rule.serialize(), "%{ for item in items }text%{ endfor }")

    def test_serialize_key_value(self):
        key = IdentifierRule([NAME("k")])
        val = IdentifierRule([NAME("v")])
        collection = IdentifierRule([NAME("m")])
        for_start = TemplateForStartRule(
            [DIRECTIVE_START(), FOR(), key, COMMA(), val, IN(), collection, RBRACE()]
        )
        body = [StringPartRule([STRING_CHARS("text")])]
        endfor = TemplateEndforRule([DIRECTIVE_START(), ENDFOR(), RBRACE()])
        rule = TemplateForRule(for_start, body, endfor)
        self.assertEqual(rule.serialize(), "%{ for k, v in m }text%{ endfor }")
