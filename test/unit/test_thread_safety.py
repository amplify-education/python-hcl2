# pylint: disable=C0103,C0114,C0115,C0116
import dataclasses
import inspect
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase

from hcl2.api import loads, parses
from hcl2.rules.base import StartRule
from hcl2.rules.containers import TupleRule
from hcl2.utils import SerializationContext, SerializationOptions

# Serializing a function call enters a `${...}` scope; the plain document
# serializes to a different type depending on whether that scope leaks.
TOGGLES_CONTEXT = "z = f([1, 2, 3], {a = 1})\n"
PLAIN = "x = [1, 2, 3]\ny = {a = 1}\n"
EXPECTED = {"x": [1, 2, 3], "y": {"a": 1}}


class TestConcurrentLoads(TestCase):
    def test_a_concurrent_parse_does_not_change_another_parse_result(self):
        def work(index):
            if index % 2:
                loads(TOGGLES_CONTEXT)
                return None
            return loads(PLAIN)

        # Below roughly 400 interleaved parses the threads rarely overlap
        # enough to expose a shared mutable context.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = [result for result in pool.map(work, range(800)) if result is not None]

        self.assertEqual(len(results), 400)
        corrupted = [result for result in results if result != EXPECTED]
        self.assertEqual(corrupted, [], f"{len(corrupted)} of {len(results)} parses were corrupted")


class TestSharedContextIsNeverWritten(TestCase):
    """Every `serialize()` shares one default context, and callers may share theirs."""

    def _record_during_nested_serialization(self, context):
        """Record `context.inside_dollar_string` while `TupleRule` runs inside `f(...)`."""
        seen = []
        original = TupleRule.serialize

        def spy(rule, options=SerializationOptions(), context_=SerializationContext()):
            seen.append(context.inside_dollar_string)
            return original(rule, options, context_)

        TupleRule.serialize = spy  # type: ignore[method-assign]
        self.addCleanup(setattr, TupleRule, "serialize", original)
        return seen

    def test_the_default_context_is_frozen_and_untouched(self):
        default = inspect.signature(StartRule.serialize).parameters["context"].default
        seen = self._record_during_nested_serialization(default)

        parses(TOGGLES_CONTEXT).serialize()

        self.assertEqual(seen, [False])
        self.assertEqual(default, SerializationContext())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            default.inside_dollar_string = True  # type: ignore[misc]

    def test_a_nested_scope_does_not_write_to_the_callers_context(self):
        shared = SerializationContext()
        seen = self._record_during_nested_serialization(shared)

        parses(TOGGLES_CONTEXT).serialize(SerializationOptions(), shared)

        self.assertEqual(seen, [False])
        self.assertEqual(shared, SerializationContext())

    def test_the_same_context_serves_concurrent_calls(self):
        shared = SerializationContext()
        with ThreadPoolExecutor(max_workers=4) as pool:
            produced = list(
                pool.map(
                    lambda src: parses(src).serialize(SerializationOptions(), shared),
                    [TOGGLES_CONTEXT, PLAIN] * 8,
                )
            )
        self.assertEqual(produced[1::2], [EXPECTED] * 8)
        self.assertEqual(shared, SerializationContext())
