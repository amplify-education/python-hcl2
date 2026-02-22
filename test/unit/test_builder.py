from unittest import TestCase

from hcl2.builder import Builder
from hcl2.const import IS_BLOCK


class TestBuilderAttributes(TestCase):

    def test_empty_builder(self):
        b = Builder()
        result = b.build()
        self.assertIn(IS_BLOCK, result)
        self.assertTrue(result[IS_BLOCK])

    def test_with_attributes(self):
        b = Builder({"key": "value", "count": 3})
        result = b.build()
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["count"], 3)

    def test_is_block_marker_present(self):
        b = Builder({"x": 1})
        result = b.build()
        self.assertTrue(result[IS_BLOCK])


class TestBuilderBlock(TestCase):

    def test_simple_block(self):
        b = Builder()
        b.block("resource")
        result = b.build()
        self.assertIn("resource", result)
        self.assertEqual(len(result["resource"]), 1)

    def test_block_with_labels(self):
        b = Builder()
        b.block("resource", labels=["aws_instance", "example"])
        result = b.build()
        block_entry = result["resource"][0]
        self.assertIn("aws_instance", block_entry)
        inner = block_entry["aws_instance"]
        self.assertIn("example", inner)

    def test_block_with_attributes(self):
        b = Builder()
        b.block("resource", labels=["type"], ami="abc-123")
        result = b.build()
        block = result["resource"][0]["type"]
        self.assertEqual(block["ami"], "abc-123")

    def test_multiple_blocks_same_type(self):
        b = Builder()
        b.block("resource", labels=["type_a"])
        b.block("resource", labels=["type_b"])
        result = b.build()
        self.assertEqual(len(result["resource"]), 2)

    def test_multiple_block_types(self):
        b = Builder()
        b.block("resource")
        b.block("data")
        result = b.build()
        self.assertIn("resource", result)
        self.assertIn("data", result)

    def test_block_returns_builder(self):
        b = Builder()
        child = b.block("resource")
        self.assertIsInstance(child, Builder)

    def test_block_child_attributes(self):
        b = Builder()
        child = b.block("resource", labels=["type"])
        child.attributes["nested_key"] = "nested_val"
        # Rebuild to pick up the changes
        result = b.build()
        block = result["resource"][0]["type"]
        self.assertEqual(block["nested_key"], "nested_val")

    def test_self_reference_raises(self):
        b = Builder()
        with self.assertRaises(ValueError):
            b.block("resource", __nested_builder__=b)


class TestBuilderNestedBlocks(TestCase):

    def test_nested_builder(self):
        b = Builder()
        inner = Builder()
        inner.block("provisioner", labels=["local-exec"], command="echo hello")
        b.block("resource", labels=["type"], __nested_builder__=inner)
        result = b.build()
        block = result["resource"][0]["type"]
        self.assertIn("provisioner", block)

    def test_nested_blocks_merged(self):
        b = Builder()
        inner = Builder()
        inner.block("sub_block", x=1)
        inner.block("sub_block", x=2)
        b.block("resource", __nested_builder__=inner)
        result = b.build()
        block = result["resource"][0]
        self.assertEqual(len(block["sub_block"]), 2)


class TestBuilderBlockMarker(TestCase):

    def test_block_marker_is_is_block(self):
        """Verify IS_BLOCK marker is used (not __start_line__/__end_line__)."""
        b = Builder({"x": 1})
        result = b.build()
        self.assertIn(IS_BLOCK, result)
        self.assertTrue(result[IS_BLOCK])
        self.assertNotIn("__start_line__", result)
        self.assertNotIn("__end_line__", result)

    def test_nested_blocks_skip_is_block_key(self):
        """_add_nested_blocks should skip IS_BLOCK when merging."""
        b = Builder()
        inner = Builder()
        inner.block("sub", val=1)
        b.block("parent", __nested_builder__=inner)
        result = b.build()
        parent_block = result["parent"][0]
        # sub blocks should be present, but IS_BLOCK from inner should not leak as a list
        self.assertIn("sub", parent_block)
        # IS_BLOCK should be a bool marker, not a list
        self.assertTrue(parent_block[IS_BLOCK])


class TestBuilderIntegration(TestCase):

    def test_full_document(self):
        doc = Builder()
        doc.block(
            "resource",
            labels=["aws_instance", "web"],
            ami="ami-12345",
            instance_type="t2.micro",
        )
        doc.block(
            "resource",
            labels=["aws_s3_bucket", "data"],
            bucket="my-bucket",
        )
        result = doc.build()
        self.assertEqual(len(result["resource"]), 2)

        web = result["resource"][0]["aws_instance"]["web"]
        self.assertEqual(web["ami"], "ami-12345")
        self.assertEqual(web["instance_type"], "t2.micro")

        data = result["resource"][1]["aws_s3_bucket"]["data"]
        self.assertEqual(data["bucket"], "my-bucket")
