"""Unit-тесты зондов app.core.diagnostics (без live БД — через моки)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.core.diagnostics import probes, runner


class TestProbeHelpers(unittest.TestCase):
    def test_ok_fail_shapes(self):
        ok = probes._ok("x", ms=1.5, detail={"a": 1}, warning="w")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["name"], "x")
        self.assertEqual(ok["warning"], "w")
        fail = probes._fail("y", "boom", ms=2.0)
        self.assertFalse(fail["ok"])
        self.assertEqual(fail["error"], "boom")


class TestProbeDatabase(unittest.TestCase):
    def test_mask_db_uri(self):
        masked = probes._mask_db_uri("postgresql://user:secret@localhost:5432/osys")
        self.assertEqual(masked, "postgresql://user:***@localhost:5432/osys")
        self.assertNotIn("secret", masked)

    @patch("app.core.diagnostics.probes.session_scope")
    def test_database_ok(self, scope_mock):
        session = MagicMock()
        session.query.return_value.limit.return_value.all.return_value = []
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = None
        scope_mock.return_value = ctx
        with patch("app.configuration.Config") as cfg:
            cfg.SQLALCHEMY_DATABASE_URI = "sqlite:///app.db"
            cfg.SQLALCHEMY_POOL_SIZE = 5
            result = probes.probe_database()
        self.assertTrue(result["ok"])
        self.assertEqual(result["name"], "database")
        self.assertEqual(result["detail"]["dialect"], "sqlite")
        self.assertEqual(result["detail"]["values_table"], "ok")
        self.assertEqual(result["detail"]["history_table"], "ok")
        session.execute.assert_called()

    @patch("app.core.diagnostics.probes.session_scope", side_effect=RuntimeError("db down"))
    def test_database_fail(self, _scope_mock):
        result = probes.probe_database()
        self.assertFalse(result["ok"])
        self.assertIn("db down", result["error"])


class TestProbeObjectsStorage(unittest.TestCase):
    def test_objects_storage_ok(self):
        storage = MagicMock()
        storage.objects = {"A": object(), "B": object()}

        with patch("app.core.main.ObjectsStorage.objects_storage", storage):
            with patch("app.core.lib.object.getObject", return_value=object()):
                result = probes.probe_objects_storage()

        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"]["objects_loaded"], 2)
        self.assertIn("avg_get_object_ms", result["detail"])


class TestProbePropertyRoundtripGuards(unittest.TestCase):
    def test_rejects_non_sandbox_name(self):
        result = probes.probe_property_roundtrip("Lamp", "state", 1)
        self.assertFalse(result["ok"])
        self.assertIn("__CoreProbe", result["error"])

    def test_rejects_external_links(self):
        prop = MagicMock()
        prop.linked = ["Mqtt"]
        prop.value = None
        obj = MagicMock()
        obj.properties = {"probe": prop}

        with patch("app.core.lib.object.getObject", return_value=obj):
            result = probes.probe_property_roundtrip("__CoreProbe", "probe", "x")

        self.assertFalse(result["ok"])
        self.assertIn("external links", result["error"])


class TestProbeThreadPools(unittest.TestCase):
    def test_reports_unhealthy_pool(self):
        unhealthy = MagicMock()
        unhealthy.is_healthy.return_value = False
        unhealthy.get_stats.return_value = MagicMock(
            active_threads=1,
            pending_tasks=0,
            completed_tasks=0,
            failed_tasks=0,
            rejected_tasks=0,
            pool_utilization=100.0,
        )

        router = MagicMock()
        router.get_stats.return_value = {
            "router_name": "linkedProperty",
            "routing_thresholds": {},
            "safe_pool": {"thread_pool": {}},
            "medium_pool": {"thread_pool": {}},
            "trusted_pool": {"thread_pool": {}},
        }
        router._safe_pool = unhealthy
        router._medium_pool = MagicMock(is_healthy=MagicMock(return_value=True))
        router._trusted_pool = MagicMock(is_healthy=MagicMock(return_value=True))

        with patch("app.core.main.ObjectManager._poolLinkedProperty", router):
            with patch("app.core.lib.common._poolSay", None):
                with patch("app.core.lib.common._poolPlaysound", None):
                    with patch("app.core.lib.common._poolNotify", None):
                        result = probes.probe_thread_pools()

        self.assertFalse(result["ok"])
        self.assertIn("unhealthy", result["error"])


class TestRunCoreDiagnostics(unittest.TestCase):
    @patch("app.core.diagnostics.runner.probe_batch_writer_stats")
    @patch("app.core.diagnostics.runner.probe_thread_pools")
    @patch("app.core.diagnostics.runner.probe_objects_storage")
    @patch("app.core.diagnostics.runner.probe_database")
    def test_read_only_aggregates(self, db, storage, pools, batch):
        db.return_value = {"name": "database", "ok": True, "ms": 1.0, "detail": {"state": "ok"}}
        storage.return_value = {
            "name": "objects_storage",
            "ok": True,
            "ms": 2.0,
            "detail": {"objects_loaded": 5, "avg_get_object_ms": 0.5},
        }
        pools.return_value = {"name": "thread_pools", "ok": True, "ms": 1.0, "detail": {"pools": {}}}
        batch.return_value = {
            "name": "batch_writer",
            "ok": True,
            "ms": 0.5,
            "detail": {"current_batch_size": 0},
            "warning": "last_error=x",
        }
        report = runner.run_core_diagnostics(mode="read_only")
        self.assertTrue(report["all_ok"])
        self.assertEqual(report["mode"], "read_only")
        self.assertEqual(len(report["checks"]), 4)
        self.assertEqual(report["metrics"]["objects_loaded"], 5)
        self.assertTrue(any("batch_writer" in w for w in report["warnings"]))

    def test_unknown_mode(self):
        report = runner.run_core_diagnostics(mode="destroy")  # type: ignore[arg-type]
        self.assertFalse(report["all_ok"])

    @patch("app.core.diagnostics.runner.probe_history_roundtrip")
    @patch("app.core.diagnostics.runner.probe_method_invoke")
    @patch("app.core.diagnostics.runner.probe_property_roundtrip")
    @patch("app.core.diagnostics.runner._ensure_sandbox_object")
    @patch("app.core.diagnostics.runner.probe_batch_writer_stats")
    @patch("app.core.diagnostics.runner.probe_thread_pools")
    @patch("app.core.diagnostics.runner.probe_objects_storage")
    @patch("app.core.diagnostics.runner.probe_database")
    def test_probe_mode(self, db, storage, pools, batch, ensure, roundtrip, invoke, history):
        for mock, name in (
            (db, "database"),
            (storage, "objects_storage"),
            (pools, "thread_pools"),
            (batch, "batch_writer"),
        ):
            mock.return_value = {"name": name, "ok": True, "ms": 1.0, "detail": {}}
        ensure.return_value = {"object": "__CoreProbe"}
        roundtrip.return_value = {
            "name": "property_roundtrip",
            "ok": True,
            "ms": 3.0,
            "detail": {"latency_ms": {"p50": 1.0, "p95": 2.0}},
        }
        invoke.return_value = {"name": "method_invoke", "ok": True, "ms": 4.0}
        history.return_value = {
            "name": "history_roundtrip",
            "ok": True,
            "ms": 5.0,
            "detail": {
                "latency_ms": {"p50": 2.0, "p95": 4.0},
                "history_rows_inserted": 3,
            },
        }
        report = runner.run_core_diagnostics(mode="probe", probe_iterations=2)
        self.assertTrue(report["all_ok"])
        self.assertEqual(report["mode"], "probe")
        self.assertIn("property_roundtrip_ms", report["metrics"])
        self.assertIn("history_roundtrip_ms", report["metrics"])
        ensure.assert_called_once()
        history.assert_called_once()


if __name__ == "__main__":
    unittest.main()
