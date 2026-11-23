"""Tests for shared MCP plugin contract helpers."""

import unittest

from app.core.lib.mcp_contract import (
    build_plugin_mcp_descriptors,
    revision_from_dict,
    validate_entity_payload,
    validate_plugin_mcp_capabilities,
)


class TestMcpContract(unittest.TestCase):
    def test_build_plugin_descriptors(self):
        caps = {
            "entities": True,
            "config_schema": True,
            "collections": [{"id": "items", "writable": True, "has_code": False, "binding_mode": "none"}],
            "operations": ["ping"],
            "operation_schemas": {"ping": {"params": {"type": "object"}}},
        }
        tools, resources, prompts = build_plugin_mcp_descriptors("Demo", caps)
        self.assertEqual(len(tools), 3)
        self.assertTrue(any(item.get("kind") == "plugin_surface" for item in tools))
        self.assertTrue(any(item.get("uri", "").endswith("/schema/items") for item in resources))
        self.assertTrue(prompts)

    def test_revision_from_dict_is_stable(self):
        first = revision_from_dict({"a": 1, "b": "x"})
        second = revision_from_dict({"b": "x", "a": 1})
        self.assertEqual(first, second)

    def test_validate_entity_payload_required(self):
        schema = {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}}
        bad = validate_entity_payload({}, schema)
        self.assertFalse(bad.get("ok"))
        ok = validate_entity_payload({"title": "ok"}, schema)
        self.assertTrue(ok.get("ok"))

    def test_validate_plugin_capabilities(self):
        ok = validate_plugin_mcp_capabilities(
            {
                "entities": True,
                "collections": [{"id": "tasks", "binding_mode": "none"}],
                "operations": ["ping"],
            }
        )
        self.assertTrue(ok.get("ok"))
        bad = validate_plugin_mcp_capabilities({"entities": True, "collections": []})
        self.assertFalse(bad.get("ok"))

    def test_validate_entity_payload_type_mismatch(self):
        schema = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        }
        bad = validate_entity_payload({"count": "1"}, schema)
        self.assertFalse(bad.get("ok"))
        self.assertTrue(any(err.get("field") == "count" for err in bad.get("errors", [])))

    def test_validate_entity_payload_enum(self):
        schema = {
            "type": "object",
            "properties": {"mode": {"type": "string", "enum": ["on", "off"]}},
        }
        bad = validate_entity_payload({"mode": "auto"}, schema)
        self.assertFalse(bad.get("ok"))

    def test_validate_entity_payload_non_object(self):
        bad = validate_entity_payload([], {"type": "object"})
        self.assertFalse(bad.get("ok"))
        self.assertEqual(bad["errors"][0]["field"], "_")

    def test_validate_plugin_capabilities_duplicate_collection_ids(self):
        bad = validate_plugin_mcp_capabilities(
            {
                "entities": True,
                "collections": [
                    {"id": "tasks", "binding_mode": "none"},
                    {"id": "tasks", "binding_mode": "property"},
                ],
            }
        )
        self.assertFalse(bad.get("ok"))
        self.assertTrue(any("duplicate collection id" in err for err in bad.get("errors", [])))

    def test_validate_plugin_capabilities_invalid_binding_mode(self):
        bad = validate_plugin_mcp_capabilities(
            {
                "entities": True,
                "collections": [{"id": "tasks", "binding_mode": "proxy"}],
            }
        )
        self.assertFalse(bad.get("ok"))


if __name__ == "__main__":
    unittest.main()
