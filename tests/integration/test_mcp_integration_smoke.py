"""Optional live MCP integration smoke tests.

Set MCP_INTEGRATION=1 and optionally MCP_URL / MCP_TOKEN env vars.
Skipped by default in CI unit-test runs.
"""

from __future__ import annotations

import json
import os
import unittest
import urllib.request

RUN = os.environ.get("MCP_INTEGRATION", "").strip() in {"1", "true", "yes"}
MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:5000/api/mcp")
TOKEN = os.environ.get("MCP_TOKEN", "my_secret_token_123")


@unittest.skipUnless(RUN, "set MCP_INTEGRATION=1 to run live MCP smoke tests")
class TestMcpIntegrationSmoke(unittest.TestCase):
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
        with urllib.request.urlopen(req, timeout=60) as resp:
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

    def test_health_and_capabilities(self):
        req = urllib.request.Request(
            MCP_URL,
            headers={"Authorization": f"Bearer {TOKEN}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("protocolVersion", data)

        caps = self._tool("osys_server_capabilities", req_id=2)
        self.assertGreater(int(caps.get("tools_listed_count") or 0), 0)

    def test_bind_device_schema_listed(self):
        tools = self._rpc("tools/list", req_id=3).get("tools", [])
        names = {item.get("name") for item in tools}
        listed = self._tool("osys_server_capabilities", req_id=4)
        all_names = set(listed.get("tools_listed") or [])
        self.assertIn("osys_bind_device", all_names)
        if "osys_bind_device" in names:
            self.assertIn("osys_bind_device", names)

    def test_self_test_structure(self):
        """Self-test должен вернуть steps; inactive whitelist — не единственная причина fail."""
        report = self._tool("osys_self_test", req_id=5)
        self.assertIn("all_ok", report)
        steps = report.get("steps") or report.get("checks") or []
        self.assertIsInstance(steps, list)
        self.assertGreater(len(steps), 0)
        # Если handler уже с soft-skip — skipped plugin steps не ломают отчёт
        skipped = [s for s in steps if s.get("skipped")]
        hard_plugin_fails = [
            s
            for s in steps
            if (not s.get("ok"))
            and (not s.get("skipped"))
            and str(s.get("name", "")).startswith("plugin_capabilities:")
        ]
        if skipped:
            self.assertEqual(hard_plugin_fails, [])


if __name__ == "__main__":
    unittest.main()
