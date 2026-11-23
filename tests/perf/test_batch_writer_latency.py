"""Perf: BatchWriter flush latency — значения и история свойств (PERF_TESTS=1)."""

from __future__ import annotations

import datetime
import os
import statistics
import time
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.core.main.ObjectManager import BatchWriter, ValueUpdate

RUN = os.environ.get("PERF_TESTS", "").strip().lower() in {"1", "true", "yes"}

# Пороги с запасом для CI runners
P95_FLUSH_MS_MAX = 500.0
P95_HISTORY_FLUSH_MS_MAX = 800.0
MIN_WRITES_PER_SEC = 200.0
MIN_HISTORY_WRITES_PER_SEC = 100.0


def _vu(
    value_id: int,
    value: str,
    *,
    save_history: bool = False,
    history_value: str | None = None,
    explicit_date: bool = False,
) -> ValueUpdate:
    return ValueUpdate(
        value_id=value_id,
        value=value,
        changed=datetime.datetime.now(),
        source="perf",
        save_history=save_history,
        history_value=history_value,
        explicit_date=explicit_date,
    )


@unittest.skipUnless(RUN, "set PERF_TESTS=1 to run performance tests")
class TestBatchWriterLatency(unittest.TestCase):
    """Мок session_scope: меряет накладные расходы BatchWriter (не диск)."""

    def setUp(self):
        self._session_scope_patcher = patch("app.core.main.ObjectManager.session_scope")
        mock_session_scope = self._session_scope_patcher.start()
        self.mock_db = MagicMock()
        # История: query().filter().all() → нет дубликатов
        self.mock_db.query.return_value.filter.return_value.all.return_value = []
        ctx = MagicMock()
        ctx.__enter__.return_value = self.mock_db
        ctx.__exit__.return_value = None
        mock_session_scope.return_value = ctx
        self._stats = [
            patch("app.core.main.ObjectManager.writeCoreSystemStatsMetric"),
            patch("app.core.main.ObjectManager.incrementCoreSystemStatsMetric"),
            patch("app.core.main.ObjectManager.flushBufferedCoreSystemStatsMetrics"),
        ]
        for p in self._stats:
            p.start()
        self.bw = BatchWriter(flush_interval=30.0)

    def tearDown(self):
        self.bw.shutdown(wait=True)
        for p in self._stats:
            p.stop()
        self._session_scope_patcher.stop()

    def test_flush_values_only_p95_and_throughput(self):
        """Только обновление Value (без History) — базовый путь."""
        durations = []
        n = 200
        t0 = time.perf_counter()
        for i in range(n):
            self.bw.add(_vu(1 + (i % 10), str(i), save_history=False))
            started = time.perf_counter()
            self.bw.flush_sync()
            durations.append((time.perf_counter() - started) * 1000.0)
        elapsed = time.perf_counter() - t0
        writes_per_sec = n / max(elapsed, 1e-6)
        sorted_d = sorted(durations)
        p95 = sorted_d[max(0, int(len(sorted_d) * 0.95) - 1)]
        self.assertLessEqual(p95, P95_FLUSH_MS_MAX, f"p95 flush {p95:.2f}ms > {P95_FLUSH_MS_MAX}")
        self.assertGreaterEqual(
            writes_per_sec, MIN_WRITES_PER_SEC, f"throughput {writes_per_sec:.1f}/s too low"
        )
        print(
            f"batch_writer values-only avg={statistics.mean(durations):.3f}ms "
            f"p95={p95:.3f}ms writes/s={writes_per_sec:.1f}"
        )

    def test_flush_with_history_p95_and_throughput(self):
        """Value + History (save_history=True) — путь записи истории свойств."""
        durations = []
        n = 200
        t0 = time.perf_counter()
        for i in range(n):
            val = str(i)
            self.bw.add(
                _vu(
                    1 + (i % 10),
                    val,
                    save_history=True,
                    history_value=val,
                    explicit_date=False,
                )
            )
            started = time.perf_counter()
            self.bw.flush_sync()
            durations.append((time.perf_counter() - started) * 1000.0)
        elapsed = time.perf_counter() - t0
        writes_per_sec = n / max(elapsed, 1e-6)
        sorted_d = sorted(durations)
        p95 = sorted_d[max(0, int(len(sorted_d) * 0.95) - 1)]

        self.assertGreater(self.mock_db.bulk_insert_mappings.call_count, 0)
        self.assertLessEqual(
            p95, P95_HISTORY_FLUSH_MS_MAX, f"history p95 flush {p95:.2f}ms > {P95_HISTORY_FLUSH_MS_MAX}"
        )
        self.assertGreaterEqual(
            writes_per_sec,
            MIN_HISTORY_WRITES_PER_SEC,
            f"history throughput {writes_per_sec:.1f}/s too low",
        )
        stats = self.bw.get_stats()
        self.assertGreaterEqual(stats["total_history_inserted"], 1)
        print(
            f"batch_writer+history avg={statistics.mean(durations):.3f}ms "
            f"p95={p95:.3f}ms writes/s={writes_per_sec:.1f} "
            f"history_inserted={stats['total_history_inserted']}"
        )

    def test_batched_history_flush_cheaper_than_one_by_one(self):
        """Пачка истории в одном flush должна быть эффективнее N одиночных flush."""
        n = 100
        # one-by-one
        t0 = time.perf_counter()
        for i in range(n):
            self.bw.add(_vu(1, str(i), save_history=True, history_value=str(i)))
            self.bw.flush_sync()
        one_by_one = time.perf_counter() - t0

        # batched
        t1 = time.perf_counter()
        for i in range(n):
            self.bw.add(_vu(2, str(i), save_history=True, history_value=str(i)))
        self.bw.flush_sync()
        batched = time.perf_counter() - t1

        self.assertLess(batched, one_by_one)
        print(f"history flush one_by_one={one_by_one*1000:.1f}ms batched={batched*1000:.1f}ms")


@unittest.skipUnless(RUN, "set PERF_TESTS=1 to run performance tests")
class TestBatchWriterHistorySqlite(unittest.TestCase):
    """Реальная in-memory SQLite: быстродействие записи History в БД."""

    def setUp(self):
        from flask import Flask
        from app.extensions import db
        from app.core.models.Clasess import Object, Value, History  # noqa: F401

        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(self.app)
        self.db = db
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.create_all()

        obj = Object(name="PerfHist", description="")
        self.db.session.add(obj)
        self.db.session.flush()
        self.value_rows = []
        for i in range(5):
            v = Value(object_id=obj.id, name=f"p{i}", value="0")
            self.db.session.add(v)
            self.value_rows.append(v)
        self.db.session.commit()
        self.value_ids = [v.id for v in self.value_rows]

        @contextmanager
        def db_session_scope():
            yield self.db.session

        self._scope = patch("app.core.main.ObjectManager.session_scope", db_session_scope)
        self._scope.start()
        self._stats = [
            patch("app.core.main.ObjectManager.writeCoreSystemStatsMetric"),
            patch("app.core.main.ObjectManager.incrementCoreSystemStatsMetric"),
            patch("app.core.main.ObjectManager.flushBufferedCoreSystemStatsMetrics"),
        ]
        for p in self._stats:
            p.start()
        self.bw = BatchWriter(flush_interval=30.0)

    def tearDown(self):
        self.bw.shutdown(wait=True)
        for p in self._stats:
            p.stop()
        self._scope.stop()
        self.db.session.remove()
        self.db.drop_all()
        self.ctx.pop()

    def test_sqlite_history_insert_throughput(self):
        from app.core.models.Clasess import History

        n = 150
        durations = []
        t0 = time.perf_counter()
        for i in range(n):
            vid = self.value_ids[i % len(self.value_ids)]
            val = f"h-{i}"
            self.bw.add(
                _vu(vid, val, save_history=True, history_value=val, explicit_date=False)
            )
            started = time.perf_counter()
            self.bw.flush_sync()
            durations.append((time.perf_counter() - started) * 1000.0)
        elapsed = time.perf_counter() - t0
        hist_count = self.db.session.query(History).count()
        self.assertGreaterEqual(hist_count, n)
        writes_per_sec = n / max(elapsed, 1e-6)
        sorted_d = sorted(durations)
        p95 = sorted_d[max(0, int(len(sorted_d) * 0.95) - 1)]
        self.assertLessEqual(p95, P95_HISTORY_FLUSH_MS_MAX)
        self.assertGreaterEqual(writes_per_sec, MIN_HISTORY_WRITES_PER_SEC)
        print(
            f"sqlite history rows={hist_count} avg={statistics.mean(durations):.3f}ms "
            f"p95={p95:.3f}ms writes/s={writes_per_sec:.1f}"
        )


if __name__ == "__main__":
    unittest.main()
