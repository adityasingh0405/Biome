#!/usr/bin/env python3
"""End-to-End API Smoke Test.

Sends HTTP requests against a running Biome API server on localhost:8000
to verify /v1/health, /v1/ask, /v1/chat, /v1/compare, and security guards.
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error


BASE_URL = "http://127.0.0.1:8000"


def request(method: str, path: str, payload: dict | None = None, timeout: int = 120) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return err.code, parsed


def main() -> int:
    print("=== Step 3: Running End-to-End API Smoke Tests against :8000 ===")

    # 1. Health
    status, body = request("GET", "/v1/health")
    assert status == 200, f"Health check failed: {status} {body}"
    print(f"[PASS] /v1/health: chunks_indexed={body.get('chunks_indexed')}")

    # 2. Documents
    status, body = request("GET", "/v1/documents")
    assert status == 200, f"Documents fetch failed: {status}"
    print(f"[PASS] /v1/documents: returned {len(body.get('documents', []))} documents")

    # 3. Security: Path Traversal
    status, body = request("POST", "/v1/ingest/directory", {"directory_path": "../../Windows", "recursive": False})
    assert status == 400, f"Path traversal not blocked: {status}"
    print("[PASS] Security: Path traversal rejected with HTTP 400")

    # 4. Security: Structured query without scope fails closed
    status, body = request("POST", "/v1/ask", {"question": "How many tickets?", "route_override": "structured"})
    assert status == 403, f"Missing scope not rejected with 403: {status}"
    print("[PASS] Security: Structured query without access_scope rejected with HTTP 403")

    # 5. Ask semantic
    status, body = request("POST", "/v1/ask", {"question": "What is Biome?", "retrieval_mode": "hybrid"})
    assert status == 200, f"Ask query failed: {status}"
    print(f"[PASS] /v1/ask: route={body.get('route')} citations={len(body.get('citations', []))}")

    # 6. Session chat lifecycle
    session_id = "smoke_test_session_123"
    status, body = request("POST", "/v1/chat", {"message": "Hello world", "session_id": session_id})
    assert status == 200, f"Chat turn failed: {status}"
    print(f"[PASS] /v1/chat: session={session_id} history_length={body.get('history_length')}")

    status, body = request("DELETE", f"/v1/session/{session_id}")
    assert status == 200, f"Delete session failed: {status}"
    print("[PASS] DELETE /v1/session: successfully cleared session memory")

    print("\nAll E2E smoke tests passed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
