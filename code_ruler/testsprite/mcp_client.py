"""Synchronous MCP client that communicates with TestSprite via JSON-RPC over stdio."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from typing import Any


class MCPClient:
    """Context-manager MCP client that spawns the TestSprite MCP server as a subprocess."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("TESTSPRITE_API_KEY", "")
        self._proc: subprocess.Popen | None = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._stderr_lines: list[str] = []
        self._stderr_thread: threading.Thread | None = None

    def __enter__(self) -> MCPClient:
        env = {**os.environ, "API_KEY": self._api_key}
        self._proc = subprocess.Popen(
            ["npx", "@testsprite/testsprite-mcp@latest"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            # Prevent parent signals (SIGINT etc.) from propagating to the MCP server
            start_new_session=True,
        )
        # Drain stderr in background to prevent pipe buffer deadlock
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()
        self._initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._proc is not None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    def _drain_stderr(self) -> None:
        """Read stderr in background so the pipe buffer never fills up."""
        assert self._proc and self._proc.stderr
        for line in self._proc.stderr:
            text = line.decode(errors="replace").rstrip()
            if text:
                self._stderr_lines.append(text)
                print(f"[TestSprite MCP] {text}", file=sys.stderr)

    def _next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id

    def _send(self, msg: dict) -> None:
        """Send a JSON-RPC message to the subprocess stdin."""
        assert self._proc and self._proc.stdin
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

    def _recv(self, expected_id: int) -> dict:
        """Read JSON-RPC messages until we get the response matching expected_id."""
        assert self._proc and self._proc.stdout
        while True:
            line = self._proc.stdout.readline()
            if not line:
                stderr_tail = "\n".join(self._stderr_lines[-20:])
                raise RuntimeError(
                    f"MCP server process ended unexpectedly. stderr:\n{stderr_tail}"
                )
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Skip notifications and messages without matching id
            if msg.get("id") == expected_id:
                return msg

    def _request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and return the response."""
        req_id = self._next_id()
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        self._send(msg)
        return self._recv(expected_id=req_id)

    def _notify(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params
        self._send(msg)

    def _initialize(self) -> None:
        """Perform the MCP initialize handshake."""
        resp = self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "code-ruler", "version": "1.0.0"},
        })
        if "error" in resp:
            raise RuntimeError(f"MCP initialize failed: {resp['error']}")
        self._notify("notifications/initialized")

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call an MCP tool and return the result content.

        Returns the parsed result dict. Raises RuntimeError on errors.
        """
        resp = self._request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        if "error" in resp:
            raise RuntimeError(f"MCP tool '{name}' error: {resp['error']}")
        result = resp.get("result", {})
        if result.get("isError"):
            content = result.get("content", [])
            error_text = " ".join(
                c.get("text", "") for c in content if c.get("type") == "text"
            )
            raise RuntimeError(f"MCP tool '{name}' returned error: {error_text}")
        return result
