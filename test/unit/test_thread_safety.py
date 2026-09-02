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
from importlib import import_module
from unittest import TestCase

from hcl2.api import loads, parses, serialize
from hcl2.rules.base import AttributeRule
from hcl2.utils import SerializationContext, SerializationOptions

# Serializing a function call is what sets `inside_dollar_string`; the plain
# document is what reads it. Interleaving the two is what made it observable.
TOGGLES_CONTEXT = "z = f([1, 2, 3], {a = 1})\n"
PLAIN = "x = [1, 2, 3]\ny = {a = 1}\n"
EXPECTED = {"x": [1, 2, 3], "y": {"a": 1}}
BLOCK = 'resource "aws_instance" "web" {\n  ami = "ami-1"\n}\n'


def _parameters_named(*names):
    """Yield every parameter with one of *names* across the shipped package.

    Walking the modules rather than naming methods means a rule added later is
    covered without anyone remembering to come back here. Three things it has
    to get right, each of which it did not at first:

    * `walk_packages`, not `iter_modules`, so a future subpackage is not
      invisible.
    * the whole of `hcl2`, not `hcl2.rules` alone -- the defaults are a
      package-wide pattern, and the serializer is not the only place they can
      appear.
    * `__func__` unwrapped before the function test, because `vars(cls)` hands
      back the descriptor for a staticmethod or classmethod and
      `inspect.isfunction` is False for those. `StringRule._serialize_part_as_value`
      takes a context and is a staticmethod, and was missed until this did.
    """
    import pkgutil

    import hcl2

    for module_info in pkgutil.walk_packages(hcl2.__path__, prefix="hcl2."):
        try:
            module = import_module(module_info.name)
        except ImportError:  # pragma: no cover - nothing optional ships today
            continue
        for class_name, cls in vars(module).items():
            if not inspect.isclass(cls) or cls.__module__ != module.__name__:
                continue
            for method_name, member in vars(cls).items():
                method = getattr(member, "__func__", member)
                if not inspect.isfunction(method):
                    continue
                parameters = inspect.signature(method).parameters
                for name in names:
                    parameter = parameters.get(name)
                    if parameter is not None:
                        yield f"{module.__name__}.{class_name}.{method_name}({name})", parameter


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

    def test_every_context_parameter_defaults_to_none(self):
        offenders = [
            name
            for name, parameter in _parameters_named("context")
            if parameter.default is not None and parameter.default is not parameter.empty
        ]
        self.assertEqual(offenders, [])

    def test_the_walk_actually_found_the_methods(self):
        # A test that asserts "no offenders" over an empty list would pass
        # while inspecting nothing at all. The floor sits just under the real
        # count, so losing a module's worth of coverage fails here rather than
        # passing quietly.
        self.assertGreaterEqual(len(list(_parameters_named("context"))), 50)

    def test_every_context_parameter_is_annotated_optional(self):
        """`None` only works if the body builds one, and mypy has to see that.

        The default alone is not the invariant: a rule written `context=None`
        whose body calls `context.modify(...)` passes the check above and then
        raises `AttributeError` for the direct caller this all exists to
        protect. Annotated, mypy reports `union-attr` on the missing guard --
        verified by deleting one.
        """
        # Only the ones that default to None: a required parameter cannot be
        # None, and calling it Optional would say something untrue.
        unannotated = [
            name
            for name, parameter in _parameters_named("context")
            if parameter.default is None and parameter.annotation is parameter.empty
        ]
        self.assertEqual(unannotated, [])


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


class TestNoDefaultOptionsIsShared(TestCase):
    """`options` carried the same declaration, and loses it for the same reason.

    Nothing in the package assigns to a `SerializationOptions`, so the shared
    default was not a live defect the way the context was. It was still the
    same construct in the same position: one mutable object handed to every
    caller that omits the argument, reachable by any subclass or hook a
    consumer writes. Keeping it would have meant defending a distinction that
    rests on nobody ever writing to it.
    """

    def test_every_options_parameter_defaults_to_none(self):
        offenders = [
            name
            for name, parameter in _parameters_named("options", "_options")
            if parameter.default is not None and parameter.default is not parameter.empty
        ]
        self.assertEqual(offenders, [])

    def test_the_walk_actually_found_the_methods(self):
        self.assertGreaterEqual(len(list(_parameters_named("options", "_options"))), 55)

    def test_every_options_parameter_is_annotated_optional(self):
        unannotated = [
            name
            for name, parameter in _parameters_named("options", "_options")
            if parameter.default is None and parameter.annotation is parameter.empty
        ]
        self.assertEqual(unannotated, [])
