# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.body import DocumentView
from hcl2.query.expressions import ConditionalView
from hcl2.query.path import parse_path
from hcl2.query.resolver import resolve_path


class TestConditionalView(TestCase):
    def _parse(self, hcl):
        return DocumentView.parse(hcl)

    def test_conditional_detected(self):
        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*"))
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], ConditionalView)

    def test_condition_property(self):
        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*"))
        cond = results[0]
        self.assertEqual(cond.condition.to_hcl().strip(), "true")

    def test_true_val_property(self):
        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*"))
        cond = results[0]
        self.assertEqual(cond.true_val.to_hcl().strip(), '"yes"')

    def test_false_val_property(self):
        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*"))
        cond = results[0]
        self.assertEqual(cond.false_val.to_hcl().strip(), '"no"')

    def test_resolve_condition_by_path(self):
        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*.condition"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].to_hcl().strip(), "true")

    def test_resolve_true_val_by_path(self):
        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*.true_val"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].to_hcl().strip(), '"yes"')

    def test_resolve_false_val_by_path(self):
        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*.false_val"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].to_hcl().strip(), '"no"')

    def test_type_name(self):
        from hcl2.query._base import view_type_name

        doc = self._parse('x = true ? "yes" : "no"\n')
        results = resolve_path(doc, parse_path("*..conditional:*"))
        self.assertEqual(view_type_name(results[0]), "conditional")

    def test_nested_conditional_in_block(self):
        hcl = 'resource "aws" "main" {\n  val = var.enabled ? "on" : "off"\n}\n'
        doc = self._parse(hcl)
        results = resolve_path(doc, parse_path("resource..conditional:*"))
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], ConditionalView)

    def test_pipe_to_condition(self):
        from hcl2.query.pipeline import (
            classify_stage,
            execute_pipeline,
            split_pipeline,
        )

        doc = self._parse('x = true ? "yes" : "no"\n')
        stages = [
            classify_stage(s) for s in split_pipeline("*..conditional:* | .condition")
        ]
        results = execute_pipeline(doc, stages)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].to_hcl().strip(), "true")

    def test_conditional_with_complex_condition(self):
        doc = self._parse('x = var.count > 0 ? "some" : "none"\n')
        results = resolve_path(doc, parse_path("*..conditional:*.condition"))
        self.assertEqual(len(results), 1)
        # The condition is a binary op
        self.assertIn(">", results[0].to_hcl())
