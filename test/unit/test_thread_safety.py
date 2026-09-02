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

import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from importlib import import_module
from unittest import TestCase

from hcl2.api import loads, parses, serialize
from hcl2.rules.base import AttributeRule, BlockRule
from hcl2.utils import SerializationContext, SerializationOptions

# Serializing a function call is what sets `inside_dollar_string`; the plain
# document is what reads it. Interleaving the two is what made it observable.
TOGGLES_CONTEXT = "z = f([1, 2, 3], {a = 1})\n"
PLAIN = "x = [1, 2, 3]\ny = {a = 1}\n"
EXPECTED = {"x": [1, 2, 3], "y": {"a": 1}}
BLOCK = 'resource "aws_instance" "web" {\n  ami = "ami-1"\n}\n'


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


class TestNoDefaultContextIsShared(TestCase):
    """No rule may declare a `SerializationContext()` default again.

    A default argument is evaluated once, at import, so any method that
    declares one hands every caller in the process the same mutable object --
    and `SerializationContext.modify` mutates in place. Threading a context
    through the four structural rules fixes the parses that start at
    `StartRule`, which is every parse the public API performs, but it leaves
    the trap armed for anything that serializes a rule directly.

    This walks the shipped rule modules rather than naming methods, so a rule
    added later is covered without anyone remembering to add it here.
    """

    def _context_parameters(self):
        import inspect
        import pkgutil

        import hcl2.rules

        for module_info in pkgutil.iter_modules(hcl2.rules.__path__):
            module = import_module(f"hcl2.rules.{module_info.name}")
            for class_name, cls in vars(module).items():
                if not inspect.isclass(cls) or cls.__module__ != module.__name__:
                    continue
                for method_name, method in vars(cls).items():
                    if not inspect.isfunction(method):
                        continue
                    parameter = inspect.signature(method).parameters.get("context")
                    if parameter is not None:
                        yield f"{module.__name__}.{class_name}.{method_name}", parameter

    def test_every_context_parameter_defaults_to_none(self):
        offenders = [
            name
            for name, parameter in self._context_parameters()
            if parameter.default is not None and parameter.default is not parameter.empty
        ]
        self.assertEqual(offenders, [])

    def test_the_walk_actually_found_the_methods(self):
        # A test that asserts "no offenders" over an empty list would pass
        # while inspecting nothing at all.
        self.assertGreater(len(list(self._context_parameters())), 30)


class TestIsolationWithoutRelyingOnScheduling(TestCase):
    """The same property as above, proved without waiting for a race.

    `TestConcurrentLoads` submits 800 parses and trusts that their critical
    sections overlap. That is how the defect was found, and it is worth
    keeping, but it can only ever be evidence: on a single-core or
    differently-scheduled machine the same run can pass over unfixed code
    because the two halves never met.

    These force the overlap instead. One thread holds a mutated context open
    on a barrier while another serializes, so a shared context is not
    something the scheduler might reveal -- it is something the assertions
    cannot avoid seeing.
    """

    SOURCE = "x = 1\n"

    def _spy_on_attribute_serialization(self, hook):
        original = AttributeRule.serialize

        def spy(rule, options=SerializationOptions(), context=None):
            context = context if context is not None else SerializationContext()
            hook(context)
            return original(rule, options, context)

        AttributeRule.serialize = spy  # type: ignore[method-assign]
        self.addCleanup(setattr, AttributeRule, "serialize", original)

    def test_two_serializations_are_handed_different_contexts(self):
        seen = []
        self._spy_on_attribute_serialization(seen.append)

        serialize(parses(self.SOURCE))
        serialize(parses(self.SOURCE))

        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], seen[1])

    def test_a_held_mutation_is_invisible_to_a_concurrent_parse(self):
        barrier = threading.Barrier(2, timeout=30)
        observed = {}

        def hook(context):
            role = threading.current_thread().name
            if role == "mutator":
                # Hold the flag set across the other thread's serialization.
                context.inside_dollar_string = True
                barrier.wait()
                observed["mutator-kept-its-own"] = context.inside_dollar_string
            else:
                barrier.wait()
                observed["observer-saw"] = context.inside_dollar_string

        self._spy_on_attribute_serialization(hook)

        trees = [parses(self.SOURCE), parses(self.SOURCE)]
        threads = [
            threading.Thread(target=serialize, args=(tree,), name=name)
            for tree, name in zip(trees, ("mutator", "observer"))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(observed, {"mutator-kept-its-own": True, "observer-saw": False})


class TestTheSharedOptionsDefaultIsNeverWritten(TestCase):
    """`options` keeps a shared default, and that is only safe while it is read-only.

    The context had to stop being a default argument because the rules mutate
    it in place. `SerializationOptions` is the same kind of object in the same
    position, and the same reasoning would condemn it -- except that nothing
    in the package assigns to it. This pins that difference, so the day
    something does write to `options`, this fails rather than the shared
    default quietly becoming a second cross-thread channel.
    """

    def _default_options(self):
        return inspect.signature(AttributeRule.serialize).parameters["options"].default

    def test_every_call_that_omits_options_gets_the_same_object(self):
        # Not an endorsement -- the premise the test below is guarding. Each
        # method evaluates its own default once, at import, so the sharing is
        # per method rather than global; either way two parses that omit
        # `options` are handed one object between them.
        seen = []
        original = BlockRule.serialize

        def spy(rule, options=SerializationOptions(), context=None):
            seen.append(options)
            return original(rule, options, context)

        BlockRule.serialize = spy  # type: ignore[method-assign]
        self.addCleanup(setattr, BlockRule, "serialize", original)

        loads(BLOCK)
        loads(BLOCK)

        self.assertEqual(len(seen), 2)
        self.assertIs(seen[0], seen[1])

    def test_parsing_does_not_write_to_it(self):
        before = asdict(self._default_options())

        loads(PLAIN)
        loads(TOGGLES_CONTEXT)
        loads(PLAIN, serialization_options=SerializationOptions(with_meta=True))

        self.assertEqual(asdict(self._default_options()), before)
