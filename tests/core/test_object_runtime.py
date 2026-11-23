"""Tests for ObjectManager ephemeral runtime state."""
import datetime
import unittest
from unittest.mock import Mock, patch

from app.core.main.ObjectManager import ObjectManager, PropertyManager, MethodManager


class TestObjectRuntime(unittest.TestCase):
    def setUp(self):
        self.mock_object = Mock()
        self.mock_object.id = 1
        self.mock_object.name = "runtime_obj"
        self.mock_object.description = "Runtime test"

    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_runtime_persists_between_calls(self, mock_now):
        mock_now.return_value = datetime.datetime.now()
        om = ObjectManager(self.mock_object)
        om.runtime["counter"] = 1
        om.runtime["counter"] += 1
        self.assertEqual(om.runtime["counter"], 2)
        self.assertIs(om.runtime, om._runtime)

    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_clear_runtime(self, mock_now):
        mock_now.return_value = datetime.datetime.now()
        om = ObjectManager(self.mock_object)
        om.runtime["flag"] = True
        om.clear_runtime()
        self.assertEqual(om.runtime, {})

    @patch("app.core.main.ObjectManager.addNotify")
    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_reactive_loop_recorded_in_runtime(self, mock_now, mock_notify):
        mock_now.return_value = datetime.datetime.now()
        om = ObjectManager(self.mock_object)

        mock_prop = Mock()
        mock_prop.id = 1
        mock_prop.name = "x"
        mock_prop.history = 0
        mock_prop.type = "str"
        mock_prop.params = None
        mock_prop.method = None
        mock_prop.linked = None

        mock_value = Mock()
        mock_value.id = 1
        mock_value.value = "0"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = ""
        mock_value.linked = None

        prop = PropertyManager(1, mock_prop, mock_value)
        om.properties["x"] = prop

        with patch("app.core.main.ObjectManager.chain_enter", return_value=False):
            with patch("app.core.main.ObjectManager.chain_format", return_value="runtime_obj.x -> runtime_obj.x"):
                result = om.setProperty("x", "1")
                self.assertFalse(result)
                self.assertIn("last_reactive_loop", om.runtime)
                self.assertEqual(om.runtime["last_reactive_loop"]["chain"], "runtime_obj.x -> runtime_obj.x")

    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_runtime_not_in_properties_dict(self, mock_now):
        mock_now.return_value = datetime.datetime.now()
        om = ObjectManager(self.mock_object)
        om.runtime["secret"] = 42
        self.assertNotIn("runtime", om.properties)
        self.assertNotIn("_runtime", om.properties)


if __name__ == "__main__":
    unittest.main()
