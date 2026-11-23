"""Тесты для SystemStats: anti-loop, exclusion, toggle, plugins."""
import unittest
from unittest.mock import Mock, patch, MagicMock
import datetime


class TestValueUpdateInternal(unittest.TestCase):
    """Тесты для ValueUpdate.internal"""

    def setUp(self):
        from app.core.main.ObjectManager import ValueUpdate
        self.ValueUpdate = ValueUpdate

    def test_internal_default_false(self):
        update = self.ValueUpdate(
            value_id=1, value="test", changed=datetime.datetime.now(),
            source="test", save_history=False
        )
        self.assertFalse(update.internal)

    def test_internal_true_when_set(self):
        update = self.ValueUpdate(
            value_id=1, value="test", changed=datetime.datetime.now(),
            source="test", save_history=False, internal=True
        )
        self.assertTrue(update.internal)


class TestBatchWriterInternalStats(unittest.TestCase):
    """Тест, что internal-запись не увеличивает external.total_added"""

    def setUp(self):
        from app.core.main.ObjectManager import BatchWriter, ValueUpdate
        self.BatchWriter = BatchWriter
        self.ValueUpdate = ValueUpdate
        # Не писать в реальную БД (value_id=1/2 = SystemVar.Started/NeedRestart)
        self._session_scope_patcher = patch('app.core.main.ObjectManager.session_scope')
        mock_session_scope = self._session_scope_patcher.start()
        mock_db_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_db_session
        mock_ctx.__exit__.return_value = None
        mock_session_scope.return_value = mock_ctx
        self.bw = BatchWriter(flush_interval=0.1)

    def tearDown(self):
        self.bw.shutdown(wait=True)
        self._session_scope_patcher.stop()
        import time
        time.sleep(0.2)

    def test_internal_added_tracked_separately(self):
        now = datetime.datetime.now()
        ext = self.ValueUpdate(1, "ext", now, "ext", False)
        internal = self.ValueUpdate(2, "int", now, "osysHome:system_stats", False, internal=True)

        self.bw.add(ext)
        self.bw.add(internal)

        stats = self.bw.get_stats()
        self.assertEqual(stats["total_added"], 2)
        self.assertEqual(stats["external"]["total_added"], 1)

    def test_internal_values_tracked_separately(self):
        self.bw._total_internal_values_updated = 5
        self.bw._total_values_updated = 10
        stats = self.bw.get_stats()
        self.assertEqual(stats["total_values_updated"], 10)
        self.assertEqual(stats["external"]["total_values_updated"], 5)

    def test_mixed_batch_last_write_wins_external(self):
        """External update after internal for same value_id counts as external."""
        now = datetime.datetime.now()
        vid = 99
        self.bw.add(self.ValueUpdate(vid, "int", now, "osysHome:system_stats", False, internal=True))
        self.bw.add(self.ValueUpdate(vid, "ext", now, "user", False, internal=False))

        with self.bw._lock:
            batch = list(self.bw._batch)
        internal_by_value_id = {}
        for item in batch:
            if not item.history_only:
                internal_by_value_id[item.value_id] = item.internal
        value_updates = {item.value_id: item for item in batch if not item.history_only}
        internal_values = sum(
            1 for vid in value_updates if internal_by_value_id.get(vid, False)
        )
        self.assertEqual(internal_values, 0)


class TestTrackStats(unittest.TestCase):
    """Тест, что при track_stats=False count_write не растёт"""

    def setUp(self):
        from app.core.main.ObjectManager import PropertyManager
        self.PropertyManager = PropertyManager
        self.mock_property = Mock()
        self.mock_property.id = 1
        self.mock_property.name = "test_prop"
        self.mock_property.description = "Test"
        self.mock_property.history = 0
        self.mock_property.type = "str"
        self.mock_property.params = None

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_value_track_stats_false(self, mock_bw, mock_user, mock_now):
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None

        prop_mgr = self.PropertyManager(1, self.mock_property, None)
        prop_mgr.value_id = 1

        initial_write = prop_mgr.count_write
        prop_mgr.setValue("test", source="test", track_stats=False)
        self.assertEqual(prop_mgr.count_write, initial_write)

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    @patch('app.core.main.ObjectManager.current_user')
    @patch('app.core.main.ObjectManager._batch_writer')
    def test_set_value_track_stats_true(self, mock_bw, mock_user, mock_now):
        mock_now.return_value = datetime.datetime.now()
        mock_user.username = None

        prop_mgr = self.PropertyManager(1, self.mock_property, None)
        prop_mgr.value_id = 1

        prop_mgr.setValue("test", source="test", track_stats=True)
        self.assertEqual(prop_mgr.count_write, 1)

    @patch('app.core.main.ObjectManager.get_now_to_utc')
    def test_get_value_track_stats_false(self, mock_now):
        mock_now.return_value = datetime.datetime.now()
        from app.core.models.Clasess import Value
        mock_value = Mock(spec=Value)
        mock_value.id = 1
        mock_value.value = "test_val"
        mock_value.changed = datetime.datetime.now()
        mock_value.source = "test"
        mock_value.linked = None

        prop_mgr = self.PropertyManager(1, self.mock_property, mock_value)
        initial_read = prop_mgr.count_read

        prop_mgr.getValue(track_stats=False)
        self.assertEqual(prop_mgr.count_read, initial_read)


class TestExcludeInternalFromAggregation(unittest.TestCase):
    """Тест, что SystemStats и _permissions исключены из агрегации collector"""

    def test_excluded_objects_contains_system_stats(self):
        from app.core.lib.constants import SYSTEM_STATS_EXCLUDED_OBJECTS
        self.assertIn("SystemStats", SYSTEM_STATS_EXCLUDED_OBJECTS)
        self.assertIn("_permissions", SYSTEM_STATS_EXCLUDED_OBJECTS)

    @patch('app.core.main.ObjectsStorage.ObjectStorage._all_props_internal')
    def test_get_stats_exclude_internal(self, mock_all_internal):
        from app.core.main.ObjectsStorage import ObjectStorage
        from app.core.main.ObjectManager import ObjectManager

        mock_all_internal.return_value = False

        storage = ObjectStorage()
        mock_obj = Mock(spec=ObjectManager)
        mock_obj.name = "TestObject"
        mock_obj.object_id = 99
        mock_obj.description = "test"
        mock_obj.properties = {}

        mock_stats = {
            "stat_properties": {},
            "stat_methods": {}
        }
        mock_obj.getStats.return_value = mock_stats
        storage.objects = {"TestObject": mock_obj}
        storage.stats = {
            "TestObject": {"count_get": 0, "last_get": None}
        }

        result = storage.getStats(exclude_internal=False)
        self.assertIn("TestObject", result)

    def test_get_stats_exclude_skip_excluded(self):
        from app.core.main.ObjectsStorage import ObjectStorage
        from app.core.lib.constants import SYSTEM_STATS_EXCLUDED_OBJECTS

        storage = ObjectStorage()
        from app.core.main.ObjectManager import ObjectManager
        mock_obj = Mock(spec=ObjectManager)
        mock_obj.name = "SystemStats"
        mock_obj.object_id = 1
        mock_obj.description = "test"
        mock_obj.properties = {}
        mock_stats = {"stat_properties": {}, "stat_methods": {}}
        mock_obj.getStats.return_value = mock_stats

        storage.objects = {"SystemStats": mock_obj}
        storage.stats = {
            "SystemStats": {"count_get": 0, "last_get": None}
        }

        result = storage.getStats(exclude_internal=True)
        self.assertNotIn("SystemStats", result)


class TestSystemStatsMetricKey(unittest.TestCase):
    def test_build_property_name(self):
        from app.core.lib.common import _system_stats_metric_key
        key = _system_stats_metric_key("P", "temp.value")
        self.assertEqual(key, "plugin_P_temp_value")


class TestSystemStatsCommonApi(unittest.TestCase):
    @patch("app.core.lib.common._is_system_stats_enabled")
    @patch("app.core.lib.object.updateProperty")
    @patch("app.core.lib.object.addObjectProperty")
    def test_write_metric_forces_track_stats_false(self, mock_add, mock_update, mock_enabled):
        from app.core.lib.common import writeSystemStatsMetric

        mock_enabled.return_value = True
        writeSystemStatsMetric("Plug", "latency_ms", 12.5)
        self.assertTrue(mock_update.called)
        _, kwargs = mock_update.call_args
        self.assertEqual(kwargs.get("track_stats"), False)

    @patch("app.core.lib.common._is_system_stats_enabled")
    @patch("app.core.lib.object.updateProperty")
    @patch("app.core.lib.object.addObjectProperty")
    @patch("app.core.lib.common._is_system_stats_metric_registered", return_value=True)
    def test_write_metric_skips_reregister_when_property_exists(
        self, mock_registered, mock_add, mock_update, mock_enabled
    ):
        from app.core.lib.common import writeSystemStatsMetric

        mock_enabled.return_value = True
        writeSystemStatsMetric("xray", "db_pool_active_connections", 0)
        mock_add.assert_not_called()
        mock_update.assert_called_once()


class TestBufferedCoreSystemStats(unittest.TestCase):
    def setUp(self):
        from app.core.lib.common import _core_stats_buffer
        with _core_stats_buffer._lock:
            _core_stats_buffer._pending.clear()

    @patch("app.core.lib.common._is_system_stats_enabled")
    @patch("app.core.lib.common._apply_core_system_stats_delta", return_value=True)
    def test_hot_metrics_buffered_until_flush(self, mock_apply, mock_enabled):
        from app.core.lib.common import (
            incrementCoreSystemStatsMetric,
            flushBufferedCoreSystemStatsMetrics,
            _core_stats_buffer,
        )

        mock_enabled.return_value = True
        incrementCoreSystemStatsMetric("property_reads", 3)
        incrementCoreSystemStatsMetric("property_reads", 2)
        self.assertFalse(mock_apply.called)
        with _core_stats_buffer._lock:
            self.assertEqual(_core_stats_buffer._pending.get("property_reads"), 5)

        flushBufferedCoreSystemStatsMetrics()
        mock_apply.assert_called_once_with("property_reads", 5)

    @patch("app.core.lib.common._is_system_stats_enabled")
    @patch("app.core.lib.common._core_stats_buffer")
    def test_disabled_skips_buffer(self, mock_buffer, mock_enabled):
        from app.core.lib.common import incrementCoreSystemStatsMetric

        mock_enabled.return_value = False
        result = incrementCoreSystemStatsMetric("property_reads", 1)
        self.assertFalse(result)
        mock_buffer.increment.assert_not_called()

    @patch("app.core.lib.common._is_system_stats_enabled")
    @patch("app.core.lib.common._apply_core_system_stats_delta", return_value=True)
    def test_non_buffered_metric_writes_immediately(self, mock_apply, mock_enabled):
        from app.core.lib.common import incrementCoreSystemStatsMetric

        mock_enabled.return_value = True
        incrementCoreSystemStatsMetric("batch_values_updated", 3)
        mock_apply.assert_called_once_with("batch_values_updated", 3, source="core")


if __name__ == "__main__":
    unittest.main()
