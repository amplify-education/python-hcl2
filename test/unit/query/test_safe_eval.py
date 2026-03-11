# pylint: disable=C0103,C0114,C0115,C0116
from unittest import TestCase

from hcl2.query.safe_eval import (
    UnsafeExpressionError,
    safe_eval,
    validate_expression,
)


class TestValidateExpression(TestCase):
    def test_simple_attribute(self):
        validate_expression("x.foo")

    def test_method_call(self):
        validate_expression("x.blocks('resource')")

    def test_safe_builtin(self):
        validate_expression("len(x)")

    def test_lambda(self):
        validate_expression("sorted(x, key=lambda b: b.name)")

    def test_comparison(self):
        validate_expression("x == 1")

    def test_boolean_ops(self):
        validate_expression("x and y or not z")

    def test_subscript(self):
        validate_expression("x[0]")

    def test_constant(self):
        validate_expression("42")

    def test_rejects_import(self):
        with self.assertRaises(UnsafeExpressionError):
            validate_expression("__import__('os')")

    def test_rejects_exec(self):
        with self.assertRaises(UnsafeExpressionError):
            validate_expression("exec('code')")

    def test_rejects_eval(self):
        with self.assertRaises(UnsafeExpressionError):
            validate_expression("eval('code')")

    def test_rejects_comprehension(self):
        with self.assertRaises(UnsafeExpressionError):
            validate_expression("[x for x in y]")

    def test_syntax_error(self):
        with self.assertRaises(UnsafeExpressionError):
            validate_expression("def foo(): pass")


class TestSafeEval(TestCase):
    def test_attribute_access(self):
        class Obj:
            name = "test_value"

        result = safe_eval("x.name", {"x": Obj()})
        self.assertEqual(result, "test_value")

    def test_method_call(self):
        result = safe_eval("x.upper()", {"x": "hello"})
        self.assertEqual(result, "HELLO")

    def test_len(self):
        result = safe_eval("len(x)", {"x": [1, 2, 3]})
        self.assertEqual(result, 3)

    def test_sorted(self):
        result = safe_eval("sorted(x)", {"x": [3, 1, 2]})
        self.assertEqual(result, [1, 2, 3])

    def test_sorted_with_key(self):
        result = safe_eval(
            "sorted(x, key=lambda i: -i)",
            {"x": [3, 1, 2]},
        )
        self.assertEqual(result, [3, 2, 1])

    def test_subscript(self):
        result = safe_eval("x[1]", {"x": [10, 20, 30]})
        self.assertEqual(result, 20)

    def test_filter_lambda(self):
        result = safe_eval(
            "list(filter(lambda i: i > 1, x))",
            {"x": [1, 2, 3]},
        )
        self.assertEqual(result, [2, 3])

    def test_boolean_ops(self):
        result = safe_eval("x and y", {"x": True, "y": False})
        self.assertFalse(result)

    def test_comparison(self):
        result = safe_eval("x == 42", {"x": 42})
        self.assertTrue(result)

    def test_restricted_no_builtins(self):
        with self.assertRaises(Exception):
            safe_eval("open('/etc/passwd')", {})

    def test_max_depth(self):
        # Build deeply nested attribute access
        expr = "x" + ".a" * 25
        with self.assertRaises(UnsafeExpressionError) as ctx:
            validate_expression(expr)
        self.assertIn("depth", str(ctx.exception))

    def test_max_node_count(self):
        # Build expression with many nodes via a wide function call
        # f(1,2,...,210) has 210 Constant + 210 arg nodes + Call + Name + Expression > 200
        args = ", ".join(["1"] * 210)
        expr = f"len([{args}])"
        with self.assertRaises(UnsafeExpressionError) as ctx:
            validate_expression(expr)
        self.assertIn("node count", str(ctx.exception))

    def test_rejects_non_attr_non_name_call(self):
        # (lambda: 1)() — Call where func is a Lambda, not Name/Attribute
        with self.assertRaises(UnsafeExpressionError) as ctx:
            validate_expression("(lambda: 1)()")
        self.assertIn("Only method calls", str(ctx.exception))
