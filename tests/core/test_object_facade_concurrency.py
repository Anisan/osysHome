"""Параллельные вызовы facade setProperty/getProperty через моки ObjectManager."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

from app.core.lib import object as object_lib


class TestObjectFacadeConcurrency(unittest.TestCase):
    def test_parallel_set_property(self):
        obj = MagicMock()
        obj.setProperty.return_value = True
        errors = []
        results = []
        lock = threading.Lock()

        def worker(i):
            try:
                ok = object_lib.setProperty(f"Probe.p{i % 3}", i, source="test", track_stats=False)
                with lock:
                    results.append(ok)
            except Exception as ex:
                with lock:
                    errors.append(ex)

        with patch.object(object_lib.objects_storage, "getObjectByName", return_value=obj):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 40)
        self.assertTrue(all(results))
        self.assertEqual(obj.setProperty.call_count, 40)

    def test_parallel_get_object(self):
        sentinel = object()
        with patch.object(object_lib.objects_storage, "getObjectByName", return_value=sentinel):
            barriers = []
            got = []

            def worker():
                got.append(object_lib.getObject("Probe"))

            threads = [threading.Thread(target=worker) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            self.assertEqual(got, [sentinel] * 20)

    def test_invalid_property_name(self):
        self.assertFalse(object_lib.setProperty("NoDot", 1))


if __name__ == "__main__":
    unittest.main()
