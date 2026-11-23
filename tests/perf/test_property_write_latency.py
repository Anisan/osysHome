"""Perf: setProperty facade latency на моках (PERF_TESTS=1)."""

from __future__ import annotations

import os
import statistics
import time
import unittest
from unittest.mock import MagicMock, patch

from app.core.lib import object as object_lib

RUN = os.environ.get("PERF_TESTS", "").strip().lower() in {"1", "true", "yes"}
P95_MS_MAX = 50.0


@unittest.skipUnless(RUN, "set PERF_TESTS=1 to run performance tests")
class TestPropertyWriteLatency(unittest.TestCase):
    def test_set_property_p95(self):
        obj = MagicMock()
        obj.setProperty.return_value = True
        latencies = []
        with patch.object(object_lib.objects_storage, "getObjectByName", return_value=obj):
            for i in range(500):
                t0 = time.perf_counter()
                ok = object_lib.setProperty("PerfObj.state", i, source="perf", track_stats=False)
                latencies.append((time.perf_counter() - t0) * 1000.0)
                self.assertTrue(ok)
        sorted_l = sorted(latencies)
        p95 = sorted_l[max(0, int(len(sorted_l) * 0.95) - 1)]
        self.assertLessEqual(p95, P95_MS_MAX, f"p95={p95:.3f}ms")
        print(f"setProperty avg={statistics.mean(latencies):.3f}ms p95={p95:.3f}ms")


if __name__ == "__main__":
    unittest.main()
