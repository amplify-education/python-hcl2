# pylint: disable=C0103,C0114,C0115,C0116
"""Concurrent calls to `loads` must not corrupt each other's values.

`serialize()` declared `context=SerializationContext()` as a default argument.
Python evaluates that once, at import, so every rule in the process shared one
mutable context -- and `expressions.py`, `functions.py` and `indexing.py` mutate
it in place through `context.modify(inside_dollar_string=True)`.

A thread serializing a function call therefore set `inside_dollar_string` for
every other thread, and any tuple or object those threads were serializing came
back as its inline HCL source (`'[1, 2, 3]'`) instead of a list. Silently: no
exception, just a different type.

The structural rules now thread the context they were given and build a fresh
one when called without it, so a parse can no longer see another parse's state.
"""

from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase

from hcl2.api import loads

# Serializing a function call is what sets `inside_dollar_string`; the plain
# document is what reads it. Interleaving the two is what made it observable.
TOGGLES_CONTEXT = "z = f([1, 2, 3], {a = 1})\n"
PLAIN = "x = [1, 2, 3]\ny = {a = 1}\n"
EXPECTED = {"x": [1, 2, 3], "y": {"a": 1}}


class TestConcurrentLoads(TestCase):
    maxDiff = None

    def test_a_concurrent_parse_does_not_change_another_parse_result(self):
        def work(index):
            if index % 2:
                loads(TOGGLES_CONTEXT)
                return None
            return loads(PLAIN)

        # 800 interleaved parses. Below roughly 400 the threads do not overlap
        # enough for the shared context to be observed at all -- measured
        # against the unfixed code, which corrupts 0/50 at 100 and 400/400 here.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = [result for result in pool.map(work, range(800)) if result is not None]

        self.assertEqual(len(results), 400)
        corrupted = [result for result in results if result != EXPECTED]
        self.assertEqual(corrupted, [], f"{len(corrupted)} of {len(results)} parses were corrupted")
