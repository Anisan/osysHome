"""Offline integration: run_core_diagnostics(read_only) на моках без live app."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.core.diagnostics import run_core_diagnostics


class TestCoreDiagnosticsOffline(unittest.TestCase):
    @patch("app.core.diagnostics.runner.probe_batch_writer_stats")
    @patch("app.core.diagnostics.runner.probe_thread_pools")
    @patch("app.core.diagnostics.runner.probe_objects_storage")
    @patch("app.core.diagnostics.runner.probe_database")
    def test_read_only_report_shape(self, db, storage, pools, batch):
        db.return_value = {"name": "database", "ok": True, "ms": 0.4, "detail": {"state": "ok"}}
        storage.return_value = {
            "name": "objects_storage",
            "ok": True,
            "ms": 1.2,
            "detail": {"objects_loaded": 3, "avg_get_object_ms": 0.2, "sample_names": ["A"]},
        }
        pools.return_value = {"name": "thread_pools", "ok": True, "ms": 0.8, "detail": {"pools": {"say": {}}}}
        batch.return_value = {
            "name": "batch_writer",
            "ok": True,
            "ms": 0.3,
            "detail": {"current_batch_size": 0, "total_errors": 0},
        }

        report = run_core_diagnostics(mode="read_only", include_plugins_hint=True)
        self.assertTrue(report["all_ok"])
        self.assertEqual(report["mode"], "read_only")
        self.assertIn("elapsed_ms", report)
        self.assertGreaterEqual(report["elapsed_ms"], 0)
        names = [c["name"] for c in report["checks"]]
        self.assertEqual(names, ["database", "objects_storage", "thread_pools", "batch_writer"])
        self.assertEqual(report["metrics"]["db_ms"], 0.4)
        self.assertIn("plugins_hint", report["metrics"])

    @patch("app.core.diagnostics.runner.probe_batch_writer_stats")
    @patch("app.core.diagnostics.runner.probe_thread_pools")
    @patch("app.core.diagnostics.runner.probe_objects_storage")
    @patch("app.core.diagnostics.runner.probe_database")
    def test_read_only_fails_when_db_down(self, db, storage, pools, batch):
        db.return_value = {"name": "database", "ok": False, "ms": 1.0, "error": "down"}
        storage.return_value = {"name": "objects_storage", "ok": True, "ms": 0.1, "detail": {}}
        pools.return_value = {"name": "thread_pools", "ok": True, "ms": 0.1, "detail": {"pools": {}}}
        batch.return_value = {"name": "batch_writer", "ok": True, "ms": 0.1, "detail": {}}
        report = run_core_diagnostics(mode="read_only")
        self.assertFalse(report["all_ok"])


if __name__ == "__main__":
    unittest.main()
