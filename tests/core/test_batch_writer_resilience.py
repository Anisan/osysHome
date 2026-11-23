"""Отказоустойчивость BatchWriter: ошибка БД, concurrent add, stats."""

from __future__ import annotations

import datetime
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from app.core.main.ObjectManager import BatchWriter, ValueUpdate, get_batch_writer_stats


class TestBatchWriterResilience(unittest.TestCase):
    def setUp(self):
        self._session_scope_patcher = patch("app.core.main.ObjectManager.session_scope")
        mock_session_scope = self._session_scope_patcher.start()
        self.mock_db_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = self.mock_db_session
        mock_ctx.__exit__.return_value = None
        mock_session_scope.return_value = mock_ctx

        # Не писать SystemStats в реальность
        self._stats_patches = [
            patch("app.core.main.ObjectManager.writeCoreSystemStatsMetric"),
            patch("app.core.main.ObjectManager.incrementCoreSystemStatsMetric"),
            patch("app.core.main.ObjectManager.flushBufferedCoreSystemStatsMetrics"),
        ]
        for p in self._stats_patches:
            p.start()

        self.bw = BatchWriter(flush_interval=30.0, max_size=0)

    def tearDown(self):
        self.bw.shutdown(wait=True)
        for p in self._stats_patches:
            p.stop()
        self._session_scope_patcher.stop()
        time.sleep(0.05)

    def _vu(self, value_id: int, value: str, *, internal: bool = False) -> ValueUpdate:
        return ValueUpdate(
            value_id=value_id,
            value=value,
            changed=datetime.datetime.now(),
            source="test",
            save_history=False,
            internal=internal,
        )

    def test_flush_success_updates_stats(self):
        self.bw.add(self._vu(10, "a"))
        self.bw.add(self._vu(11, "b"))
        self.bw.flush_sync()
        stats = self.bw.get_stats()
        self.assertEqual(stats["current_batch_size"], 0)
        self.assertGreaterEqual(stats["total_flushed"], 1)
        self.assertGreaterEqual(stats["external"]["total_added"], 2)

    def test_db_error_requeues_and_counts_external_error(self):
        self.mock_db_session.bulk_update_mappings.side_effect = RuntimeError("db boom")
        self.bw.add(self._vu(20, "x"))
        self.bw.flush_sync()
        stats = self.bw.get_stats()
        self.assertGreaterEqual(stats["total_errors"], 1)
        self.assertIsNotNone(stats["last_error"])
        self.assertGreaterEqual(stats["current_batch_size"], 1)

    def test_internal_only_error_tracked_separately(self):
        self.mock_db_session.bulk_update_mappings.side_effect = RuntimeError("db boom")
        self.bw.add(self._vu(21, "int", internal=True))
        self.bw.flush_sync()
        stats = self.bw.get_stats()
        # external errors не растут, если батч только internal
        self.assertEqual(stats["total_errors"], 0)
        self.assertGreaterEqual(stats.get("total_internal_errors", 0), 1)

    def test_concurrent_add(self):
        errors = []

        def worker(start_id):
            try:
                for i in range(50):
                    self.bw.add(self._vu(start_id + i, str(i)))
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=worker, args=(1000 + n * 100,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(errors, [])
        stats = self.bw.get_stats()
        self.assertEqual(stats["total_added"], 200)

    def test_max_size_triggers_async_flush(self):
        bw = BatchWriter(flush_interval=30.0, max_size=3)
        try:
            with patch.object(bw, "flush") as flush_mock:
                bw.add(self._vu(1, "1"))
                bw.add(self._vu(2, "2"))
                flush_mock.assert_not_called()
                bw.add(self._vu(3, "3"))
                flush_mock.assert_called()
        finally:
            bw.shutdown(wait=True)

    def test_get_batch_writer_stats_public(self):
        stats = get_batch_writer_stats()
        self.assertIn("current_batch_size", stats)
        self.assertIn("worker_thread_alive", stats)


if __name__ == "__main__":
    unittest.main()
