"""Live diagnostics через MCP (CORE_LIVE_DIAG=1 или MCP_INTEGRATION=1)."""

from __future__ import annotations

import json
import os
import unittest
import urllib.request

RUN = os.environ.get("CORE_LIVE_DIAG", "").strip().lower() in {"1", "true", "yes"} or (
    os.environ.get("MCP_INTEGRATION", "").strip().lower() in {"1", "true", "yes"}
)
MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5000/api/mcp")
TOKEN = os.environ.get("MCP_TOKEN", "my_secret_token_123")
RUN_PROBE = os.environ.get("CORE_LIVE_PROBE", "").strip().lower() in {"1", "true", "yes"}


@unittest.skipUnless(RUN, "set CORE_LIVE_DIAG=1 or MCP_INTEGRATION=1 for live diagnostics")
class TestLiveCoreDiagnostics(unittest.TestCase):
    def _rpc(self, method: str, params: dict | None = None, req_id: int = 1) -> dict:
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        req = urllib.request.Request(
            MCP_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            raise AssertionError(json.dumps(data["error"], ensure_ascii=False))
        return data.get("result", {})

    def _tool(self, name: str, arguments: dict | None = None, req_id: int = 1) -> dict:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}}, req_id=req_id)
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result

    def test_health_shape(self):
        health = self._tool("osys_health", req_id=10)
        self.assertIn("ok", health)
        self.assertIn("database", health)
        self.assertIn("objects_loaded", health)

    def test_self_test_report_shape(self):
        report = self._tool("osys_self_test", req_id=11)
        self.assertIn("all_ok", report)
        steps = report.get("steps") or report.get("checks") or []
        self.assertIsInstance(steps, list)
        self.assertGreater(len(steps), 0)
        # Inactive whitelist plugin must not hard-fail via skipped steps alone
        hard_fails = [
            s
            for s in steps
            if not s.get("ok") and not s.get("skipped") and "plugin_capabilities:" in str(s.get("name"))
        ]
        self.assertEqual(hard_fails, [])
        # Prefer core metrics when new handler is deployed
        if "metrics" in report:
            self.assertIsInstance(report["metrics"], dict)

    @unittest.skipUnless(RUN_PROBE, "set CORE_LIVE_PROBE=1 for sandbox write probe")
    def test_self_test_probe(self):
        report = self._tool(
            "osys_self_test_probe",
            {"iterations": 3, "delete_sandbox": False},
            req_id=12,
        )
        self.assertIn("all_ok", report)
        self.assertEqual(report.get("mode"), "probe")
        self.assertTrue(report.get("all_ok"), json.dumps(report, ensure_ascii=False)[:1000])


if __name__ == "__main__":
    unittest.main()
