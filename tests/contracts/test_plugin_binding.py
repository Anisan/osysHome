"""Tests for plugin binding helpers."""

import unittest
from unittest.mock import MagicMock, patch

from app.core.lib import plugin_binding


class TestPluginBinding(unittest.TestCase):
  @patch("app.core.lib.plugin_binding.objects_storage")
  def test_validate_object_exists(self, storage_mock):
    storage_mock.getObjectByName.return_value = object()
    self.assertTrue(plugin_binding.validate_object_exists("Lamp"))
    storage_mock.getObjectByName.return_value = None
    self.assertFalse(plugin_binding.validate_object_exists("Missing"))

  @patch("app.core.lib.plugin_binding.setLinkToObject")
  @patch("app.core.lib.plugin_binding.removeLinkFromObject")
  @patch("app.core.lib.plugin_binding.validate_object_property_exists")
  def test_sync_property_link_add(self, validate_mock, remove_mock, set_mock):
    validate_mock.return_value = True
    set_mock.return_value = True
    ok, err = plugin_binding.sync_property_link("Mqtt", "Lamp", "state")
    self.assertTrue(ok)
    self.assertIsNone(err)
    set_mock.assert_called_once_with("Lamp", "state", "Mqtt")
    remove_mock.assert_not_called()

  @patch("app.core.lib.plugin_binding.setLinkToObject")
  @patch("app.core.lib.plugin_binding.removeLinkFromObject")
  @patch("app.core.lib.plugin_binding.validate_object_property_exists")
  def test_sync_property_link_replace(self, validate_mock, remove_mock, set_mock):
    validate_mock.return_value = True
    set_mock.return_value = True
    ok, err = plugin_binding.sync_property_link(
      "Mqtt",
      "Lamp2",
      "power",
      old_object="Lamp",
      old_property="state",
    )
    self.assertTrue(ok)
    self.assertIsNone(err)
    remove_mock.assert_called_once_with("Lamp", "state", "Mqtt")
    set_mock.assert_called_once_with("Lamp2", "power", "Mqtt")

  @patch("app.core.lib.plugin_binding.setLinkToObject")
  @patch("app.core.lib.plugin_binding.removeLinkFromObject")
  @patch("app.core.lib.plugin_binding.validate_object_property_exists")
  def test_sync_property_link_missing_object_property(self, validate_mock, remove_mock, set_mock):
    validate_mock.return_value = False
    ok, err = plugin_binding.sync_property_link("Mqtt", "Missing", "state")
    self.assertFalse(ok)
    self.assertEqual(err, "Object property not found: Missing.state")
    set_mock.assert_not_called()
    remove_mock.assert_not_called()

  @patch("app.core.lib.plugin_binding.setLinkToObject")
  @patch("app.core.lib.plugin_binding.removeLinkFromObject")
  @patch("app.core.lib.plugin_binding.validate_object_property_exists")
  def test_sync_property_link_set_link_failure(self, validate_mock, remove_mock, set_mock):
    validate_mock.return_value = True
    set_mock.return_value = False
    ok, err = plugin_binding.sync_property_link("Mqtt", "Lamp", "state")
    self.assertFalse(ok)
    self.assertEqual(err, "Failed to set link for Lamp.state")

  def test_sync_property_link_requires_plugin_name(self):
    ok, err = plugin_binding.sync_property_link("", "Lamp", "state")
    self.assertFalse(ok)
    self.assertEqual(err, "plugin_name is required")

  def test_sync_property_link_requires_both_names(self):
    ok, err = plugin_binding.sync_property_link("Mqtt", "Lamp", "")
    self.assertFalse(ok)
    self.assertEqual(err, "linked_property is required when linked_object is set")
    ok, err = plugin_binding.sync_property_link("Mqtt", "", "state")
    self.assertFalse(ok)
    self.assertEqual(err, "linked_object is required when linked_property is set")

  @patch("app.core.lib.plugin_binding.objects_storage")
  def test_sync_object_link_missing_object(self, storage_mock):
    storage_mock.getObjectByName.return_value = None
    ok, err = plugin_binding.sync_object_link("Missing")
    self.assertFalse(ok)
    self.assertEqual(err, "Object not found: Missing")

  @patch("app.core.lib.plugin_binding.removeLinkFromObject", return_value=True)
  def test_remove_property_link_noop_on_empty(self, remove_mock):
    self.assertTrue(plugin_binding.remove_property_link("Mqtt", "", "state"))
    remove_mock.assert_not_called()


if __name__ == "__main__":
  unittest.main()
