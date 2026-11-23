"""Tests for object lifecycle hooks onInit/onStop."""
import datetime
import unittest
from unittest.mock import MagicMock, Mock, patch

from app.core.main.ObjectsStorage import ObjectStorage
from app.core.main.ObjectManager import ObjectManager, MethodManager


class TestLifecycleHooks(unittest.TestCase):
    def setUp(self):
        self._cleaner_patcher = patch.object(ObjectStorage, "clean_task", return_value=None)
        self._cleaner_patcher.start()
        self.storage = ObjectStorage()
        self.storage._stop_event.set()
        self.storage.cleaner_thread.join(timeout=1.0)

    def tearDown(self):
        self.storage._stop_event.set()
        if self.storage.cleaner_thread.is_alive():
            self.storage.cleaner_thread.join(timeout=1.0)
        self._cleaner_patcher.stop()

    def _make_om(self, name="hook_obj"):
        mock_obj = Mock()
        mock_obj.id = 1
        mock_obj.name = name
        mock_obj.description = ""
        om = ObjectManager(mock_obj)
        om.methods["onInit"] = MethodManager([{"name": "onInit", "description": "", "owner": "Test"}])
        om.methods["onStop"] = MethodManager([{"name": "onStop", "description": "", "owner": "Test"}])
        return om

    @patch("app.core.main.ObjectManager.ObjectManager.callMethod")
    def test_invoke_lifecycle_calls_method(self, mock_call):
        om = self._make_om()
        self.storage._invoke_lifecycle(om, "onInit")
        mock_call.assert_called_once_with("onInit", source="system:onInit")

    @patch("app.core.main.ObjectManager.ObjectManager.callMethod")
    def test_invoke_lifecycle_skips_missing_hook(self, mock_call):
        om = self._make_om()
        del om.methods["onStop"]
        self.storage._invoke_lifecycle(om, "onStop")
        mock_call.assert_not_called()

    @patch("app.core.main.ObjectManager.ObjectManager.callMethod")
    def test_invoke_lifecycle_prevents_recursion(self, mock_call):
        om = self._make_om()
        om._lifecycle_running = True
        self.storage._invoke_lifecycle(om, "onInit")
        mock_call.assert_not_called()

    @patch("app.core.main.ObjectsStorage.get_now_to_utc")
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_get_object_by_name_calls_on_init_once(self, mock_session_scope, mock_now):
        mock_now.return_value = datetime.datetime.now()
        om = self._make_om("lazy_obj")

        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_db_obj = Mock()
        mock_db_obj.name = "lazy_obj"
        mock_session.query.return_value.filter_by.return_value.one_or_none.return_value = mock_db_obj

        with patch.object(self.storage, "_createObjectManager", return_value=om):
            with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
                first = self.storage.getObjectByName("lazy_obj")
                second = self.storage.getObjectByName("lazy_obj")
                self.assertIs(first, second)
                mock_lifecycle.assert_called_once_with(om, "onInit")

    @patch("app.core.main.ObjectsStorage.get_now_to_utc")
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_replace_object_manager_lifecycle(self, mock_session_scope, mock_now):
        mock_now.return_value = datetime.datetime.now()
        old_om = self._make_om("reload_obj")
        new_om = self._make_om("reload_obj")
        self.storage.objects["reload_obj"] = old_om

        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_db_obj = Mock()
        mock_db_obj.name = "reload_obj"

        with patch.object(self.storage, "_createObjectManager", return_value=new_om):
            with patch("app.core.main.ObjectManager.ObjectManager.clear_runtime") as mock_clear:
                with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
                    self.storage._replace_object_manager(mock_session, mock_db_obj)
                    calls = [c.args for c in mock_lifecycle.call_args_list]
                    self.assertEqual(calls[0], (old_om, "onStop"))
                    self.assertEqual(calls[1], (new_om, "onInit"))
                    mock_clear.assert_called_once()

    @patch("app.core.main.ObjectsStorage.get_now_to_utc")
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_reload_object_loads_new_object(self, mock_session_scope, mock_now):
        mock_now.return_value = datetime.datetime.now()
        om = self._make_om("new_obj")

        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_db_obj = Mock()
        mock_db_obj.id = 42
        mock_db_obj.name = "new_obj"
        mock_session.query.return_value.filter.return_value.one_or_none.return_value = mock_db_obj

        with patch.object(self.storage, "_createObjectManager", return_value=om):
            with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
                self.storage.reload_object(42)
                self.assertIs(self.storage.objects["new_obj"], om)
                mock_lifecycle.assert_called_once_with(om, "onInit")

    @patch("app.core.main.ObjectsStorage.get_now_to_utc")
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_reload_object_refreshes_cached_object(self, mock_session_scope, mock_now):
        mock_now.return_value = datetime.datetime.now()
        old_om = self._make_om("reload_obj")
        new_om = self._make_om("reload_obj")
        self.storage.objects["reload_obj"] = old_om

        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_db_obj = Mock()
        mock_db_obj.id = 7
        mock_db_obj.name = "reload_obj"
        mock_session.query.return_value.filter.return_value.one_or_none.return_value = mock_db_obj

        with patch.object(self.storage, "_createObjectManager", return_value=new_om):
            with patch("app.core.main.ObjectManager.ObjectManager.clear_runtime"):
                with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
                    self.storage.reload_object(7)
                    self.assertIs(self.storage.objects["reload_obj"], new_om)
                    calls = [c.args for c in mock_lifecycle.call_args_list]
                    self.assertEqual(calls[0], (old_om, "onStop"))
                    self.assertEqual(calls[1], (new_om, "onInit"))

    @patch("app.core.main.ObjectsStorage.get_now_to_utc")
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_sync_removed_evicts_deleted_object(self, mock_session_scope, mock_now):
        mock_now.return_value = datetime.datetime.now()
        om = self._make_om("gone_obj")
        self.storage.objects["gone_obj"] = om

        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.all.return_value = []
        mock_session.query.return_value.filter_by.return_value.one_or_none.return_value = None

        with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
            removed = self.storage.sync_removed()
            self.assertEqual(removed, 1)
            self.assertNotIn("gone_obj", self.storage.objects)
            mock_lifecycle.assert_called_once_with(om, "onStop")

    def test_runtime_map_items_triggers_sync_missing(self):
        with patch.object(self.storage, "sync_missing", return_value=0) as mock_sync:
            list(self.storage.objects.items())
            mock_sync.assert_called_once()

    @patch("app.core.main.ObjectsStorage.get_now_to_utc")
    @patch("app.core.main.ObjectsStorage.session_scope")
    def test_sync_missing_loads_only_absent_objects(self, mock_session_scope, mock_now):
        mock_now.return_value = datetime.datetime.now()
        existing = self._make_om("existing")
        loaded = self._make_om("loaded")
        self.storage.objects["existing"] = existing

        db_existing = Mock()
        db_existing.name = "existing"
        db_loaded = Mock()
        db_loaded.name = "loaded"

        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.order_by.return_value.all.return_value = [
            db_existing,
            db_loaded,
        ]

        with patch.object(self.storage, "_createObjectManager", side_effect=[loaded]) as mock_create:
            with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
                count = self.storage.sync_missing()
                self.assertEqual(count, 1)
                self.assertIs(self.storage.objects["loaded"], loaded)
                mock_create.assert_called_once_with(mock_session, db_loaded)
                mock_lifecycle.assert_called_once_with(loaded, "onInit")

    def test_sync_cache_runs_removed_before_missing(self):
        with patch.object(self.storage, "sync_removed", return_value=1) as mock_removed:
            with patch.object(self.storage, "sync_missing", return_value=2) as mock_missing:
                self.storage.sync_cache()
                self.assertEqual(mock_removed.call_count, 1)
                self.assertEqual(mock_missing.call_count, 1)

    def test_remove_object_evicts_from_cache(self):
        old_om = self._make_om("evicted_object")
        self.storage.objects["evicted_object"] = old_om
        self.storage.stats["evicted_object"] = {"count_get": 1, "last_get": datetime.datetime.now()}
        self.storage.clean_objects["evicted_object"] = {"dt": datetime.datetime.now(), "count": 0, "result": {}}

        with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
            self.storage.remove_object("evicted_object")

        self.assertNotIn("evicted_object", self.storage.objects)
        self.assertNotIn("evicted_object", self.storage.stats)
        self.assertNotIn("evicted_object", self.storage.clean_objects)
        mock_lifecycle.assert_called_once_with(old_om, "onStop")

    def test_remove_object_noop_for_unknown_name(self):
        with patch.object(self.storage, "_invoke_lifecycle") as mock_lifecycle:
            self.storage.remove_object("unknown_object")

        mock_lifecycle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
