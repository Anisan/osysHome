"""Tests for background object preload."""
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

from app.core.main.ObjectsStorage import ObjectStorage


class TestBackgroundPreload(unittest.TestCase):
    def setUp(self):
        self.storage = ObjectStorage()
        self.storage._stop_event.set()
        self.storage.cleaner_thread.join(timeout=1.0)

    @patch("app.core.main.ObjectsStorage.Config.OBJECT_PRELOAD_ENABLED", False)
    def test_preload_disabled(self):
        self.storage.start_background_preload()
        self.assertIsNone(self.storage._preload_thread)

    @patch("app.core.main.ObjectsStorage.Config.OBJECT_PRELOAD_BATCH_SIZE", 2)
    @patch("app.core.main.ObjectsStorage.Config.OBJECT_PRELOAD_INTERVAL_SEC", 0.01)
    @patch("app.core.main.ObjectsStorage.Config.OBJECT_PRELOAD_ENABLED", True)
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_background_preload_batches(self, mock_session_scope):
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        obj_a = Mock(name="obj_a")
        obj_a.name = "A"
        obj_b = Mock(name="obj_b")
        obj_b.name = "B"
        obj_c = Mock(name="obj_c")
        obj_c.name = "C"
        mock_session.query.return_value.order_by.return_value.all.return_value = [obj_a, obj_b, obj_c]

        existing = Mock()
        existing.name = "existing"
        self.storage.objects["existing"] = existing

        loaded = []

        def fake_get(name):
            if name not in self.storage.objects:
                self.storage.objects[name] = Mock(name=name)
            loaded.append(name)

        with patch.object(self.storage, "getObjectByName", side_effect=fake_get):
            self.storage._background_preload_worker(app=None)
            self.assertEqual(loaded, ["A", "B", "C"])
            self.assertIn("existing", self.storage.objects)

    @patch("app.core.main.ObjectsStorage.Config.OBJECT_PRELOAD_ENABLED", True)
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_start_and_stop_preload(self, mock_session_scope):
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.order_by.return_value.all.return_value = []

        self.storage.start_background_preload()
        self.assertIsNotNone(self.storage._preload_thread)
        time.sleep(0.05)
        self.storage.stop_background_preload()
        self.assertFalse(self.storage._preload_thread.is_alive())


if __name__ == "__main__":
    unittest.main()
