"""Offline integration: setProperty → linked plugin.changeLinkedProperty → method."""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

from app.core.main.ObjectManager import ObjectManager, PropertyManager


class TestPropertyBindingChain(unittest.TestCase):
    def setUp(self):
        self.mock_object = Mock()
        self.mock_object.id = 42
        self.mock_object.name = "BindProbe"
        self.mock_object.description = "binding chain"

        self.received = []
        self.event = threading.Event()

        self.plugin = MagicMock()
        self.plugin.name = "FakeBind"

        def on_change(object_name, property_name, value):
            self.received.append((object_name, property_name, value))
            self.event.set()

        self.plugin.changeLinkedProperty.side_effect = on_change

    @patch("app.core.main.ObjectManager.getModulesByAction", return_value=[])
    @patch("app.core.main.ObjectManager.getModule")
    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_set_property_notifies_linked_plugin(self, mock_now, get_module, _proxy):
        import datetime

        mock_now.return_value = datetime.datetime.now()
        get_module.return_value = self.plugin

        mock_property = Mock()
        mock_property.id = 1
        mock_property.name = "state"
        mock_property.description = "state"
        mock_property.history = 0
        mock_property.type = "str"
        mock_property.params = None
        mock_property.method = None
        mock_property.linked = None

        mock_value = Mock()
        mock_value.id = 100
        mock_value.value = "0"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = ""
        mock_value.linked = None

        prop = PropertyManager(42, mock_property, mock_value)
        prop.linked = ["FakeBind"]

        om = ObjectManager(self.mock_object)
        om.properties["state"] = prop

        with patch.object(prop, "setValue") as set_value:
            set_value.side_effect = lambda *a, **k: setattr(mock_value, "value", a[0] if a else "1") or True
            with patch.object(prop, "getValue", return_value="1"):
                ok = om.setProperty("state", "1", source="test")

        self.assertTrue(ok)
        self.assertTrue(self.event.wait(timeout=5), "changeLinkedProperty not called in time")
        self.assertEqual(self.received[0][0], "BindProbe")
        self.assertEqual(self.received[0][1], "state")
        get_module.assert_called_with("FakeBind")

    @patch("app.core.main.ObjectManager.getModulesByAction", return_value=[])
    @patch("app.core.main.ObjectManager.getModule")
    @patch("app.core.main.ObjectManager.get_now_to_utc")
    def test_property_method_invoked_on_change(self, mock_now, get_module, _proxy):
        import datetime

        mock_now.return_value = datetime.datetime.now()
        get_module.return_value = None

        mock_property = Mock()
        mock_property.id = 2
        mock_property.name = "temp"
        mock_property.description = "temp"
        mock_property.history = 0
        mock_property.type = "str"
        mock_property.params = None
        mock_property.method = "onChange"
        mock_property.linked = None

        mock_value = Mock()
        mock_value.id = 101
        mock_value.value = "0"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = ""
        mock_value.linked = None

        prop = PropertyManager(42, mock_property, mock_value)
        prop.method = "onChange"  # bindMethod вызывается отдельно при загрузке объекта
        om = ObjectManager(self.mock_object)
        om.properties["temp"] = prop

        called = {}

        def fake_call(self, method_name, args=None, source=""):
            called["method"] = method_name
            called["args"] = args
            called["source"] = source
            return "ok"

        with patch.object(prop, "setValue", return_value=True):
            with patch.object(prop, "getValue", return_value="7"):
                # ObjectManager.__setattr__ перехватывает setattr — патчим класс
                with patch.object(ObjectManager, "callMethod", fake_call):
                    ok = om.setProperty("temp", "7", source="sensor")

        self.assertTrue(ok)
        self.assertEqual(called.get("method"), "onChange")
        self.assertEqual(called["args"]["NEW_VALUE"], "7")
        self.assertIn("property:BindProbe.temp", called["source"])


if __name__ == "__main__":
    unittest.main()
