# pylint: disable=C0103,C0114,C0115,C0116
import json
from unittest import TestCase

from hcl2.query.diff import DiffEntry, diff_dicts, format_diff_json, format_diff_text


class TestDiffDicts(TestCase):
    def test_identical(self):
        d = {"a": 1, "b": "hello"}
        self.assertEqual(diff_dicts(d, d), [])

    def test_added_key(self):
        left = {"a": 1}
        right = {"a": 1, "b": 2}
        entries = diff_dicts(left, right)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].kind, "added")
        self.assertEqual(entries[0].path, "b")
        self.assertEqual(entries[0].right, 2)

    def test_removed_key(self):
        left = {"a": 1, "b": 2}
        right = {"a": 1}
        entries = diff_dicts(left, right)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].kind, "removed")
        self.assertEqual(entries[0].path, "b")
        self.assertEqual(entries[0].left, 2)

    def test_changed_value(self):
        left = {"a": 1}
        right = {"a": 2}
        entries = diff_dicts(left, right)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].kind, "changed")
        self.assertEqual(entries[0].left, 1)
        self.assertEqual(entries[0].right, 2)

    def test_nested_change(self):
        left = {"a": {"b": 1}}
        right = {"a": {"b": 2}}
        entries = diff_dicts(left, right)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].path, "a.b")
        self.assertEqual(entries[0].kind, "changed")

    def test_list_added_element(self):
        left = {"items": [1, 2]}
        right = {"items": [1, 2, 3]}
        entries = diff_dicts(left, right)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].path, "items[2]")
        self.assertEqual(entries[0].kind, "added")

    def test_list_removed_element(self):
        left = {"items": [1, 2, 3]}
        right = {"items": [1, 2]}
        entries = diff_dicts(left, right)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].path, "items[2]")
        self.assertEqual(entries[0].kind, "removed")

    def test_empty_dicts(self):
        self.assertEqual(diff_dicts({}, {}), [])

    def test_multiple_changes(self):
        left = {"a": 1, "b": 2, "c": 3}
        right = {"a": 1, "b": 99, "d": 4}
        entries = diff_dicts(left, right)
        kinds = {e.path: e.kind for e in entries}
        self.assertEqual(kinds["b"], "changed")
        self.assertEqual(kinds["c"], "removed")
        self.assertEqual(kinds["d"], "added")


class TestFormatDiffText(TestCase):
    def test_empty(self):
        self.assertEqual(format_diff_text([]), "")

    def test_added(self):
        entries = [DiffEntry(path="x", kind="added", right=42)]
        text = format_diff_text(entries)
        self.assertIn("+ x:", text)
        self.assertIn("42", text)

    def test_removed(self):
        entries = [DiffEntry(path="x", kind="removed", left="old")]
        text = format_diff_text(entries)
        self.assertIn("- x:", text)
        self.assertIn("'old'", text)

    def test_changed(self):
        entries = [DiffEntry(path="x", kind="changed", left=1, right=2)]
        text = format_diff_text(entries)
        self.assertIn("~ x:", text)
        self.assertIn("->", text)


class TestFormatDiffJson(TestCase):
    def test_json_output(self):
        entries = [
            DiffEntry(path="a", kind="added", right=1),
            DiffEntry(path="b", kind="removed", left=2),
        ]
        data = json.loads(format_diff_json(entries))
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["kind"], "added")
        self.assertEqual(data[1]["kind"], "removed")
