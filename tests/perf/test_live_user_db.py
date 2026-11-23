"""Live perf на БД из config.yaml пользователя (PERF_LIVE_DB=1).

Требует запущенное/инициализированное приложение с реальной
``Config.SQLALCHEMY_DATABASE_URI`` (SQLite/Postgres/MySQL — как настроено).
Пишет только в sandbox ``__CoreProbe`` и по умолчанию чистит History-строки пробы.
"""

from __future__ import annotations

import os
import unittest

RUN = os.environ.get("PERF_LIVE_DB", "").strip().lower() in {"1", "true", "yes"}


@unittest.skipUnless(RUN, "set PERF_LIVE_DB=1 to run against user-configured database")
class TestLiveUserDatabase(unittest.TestCase):
    def test_diagnostics_probe_on_configured_db(self):
        from app.configuration import Config
        from app.core.diagnostics import run_core_diagnostics

        uri = str(getattr(Config, "SQLALCHEMY_DATABASE_URI", "") or "")
        self.assertTrue(uri, "SQLALCHEMY_DATABASE_URI empty — check config.yaml")

        report = run_core_diagnostics(
            mode="probe",
            probe_iterations=3,
            history_iterations=3,
            include_history=True,
            cleanup_history_rows=True,
            delete_sandbox=False,
        )
        db_check = next((c for c in report["checks"] if c["name"] == "database"), None)
        self.assertIsNotNone(db_check)
        self.assertTrue(db_check["ok"], db_check)
        detail = db_check.get("detail") or {}
        self.assertEqual(detail.get("values_table"), "ok")
        self.assertEqual(detail.get("history_table"), "ok")
        self.assertIn("uri_masked", detail)
        masked = detail.get("uri_masked") or ""
        # Пароль не должен светиться в отчёте
        if "@" in masked and "://" in masked:
            creds = masked.split("://", 1)[1].split("@", 1)[0]
            if ":" in creds:
                _user, password = creds.split(":", 1)
                self.assertEqual(password, "***")


        hist = next((c for c in report["checks"] if c["name"] == "history_roundtrip"), None)
        self.assertIsNotNone(hist)
        self.assertTrue(report["all_ok"], report)
        self.assertTrue(hist["ok"], hist)
        self.assertGreaterEqual((hist.get("detail") or {}).get("history_rows_inserted", 0), 3)
        print(
            f"live DB dialect={detail.get('dialect')} uri={detail.get('uri_masked')} "
            f"history_p95={(hist.get('detail') or {}).get('latency_ms', {}).get('p95')}ms"
        )


if __name__ == "__main__":
    unittest.main()
