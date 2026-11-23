"""Tests for plugin MCP contract defaults on BasePlugin."""

import unittest

from app.core.main.BasePlugin import BasePlugin


class _DummyPlugin(BasePlugin):
  def __init__(self):
    self.name = "Dummy"
    self.config = {}

  def initialization(self):
    pass

  def admin(self, request):
    return ""


class TestPluginMcpContract(unittest.TestCase):
  def test_default_capabilities(self):
    plugin = _DummyPlugin()
    caps = plugin.mcp_capabilities()
    self.assertEqual(caps.get("mcp_version"), 1)
    self.assertFalse(caps.get("entities"))
    self.assertEqual(caps.get("collections"), [])
    self.assertFalse(plugin.mcp_supported())

  def test_unsupported_collection_raises(self):
    plugin = _DummyPlugin()
    with self.assertRaises(NotImplementedError):
      plugin.mcp_list_entities("items")


if __name__ == "__main__":
  unittest.main()
