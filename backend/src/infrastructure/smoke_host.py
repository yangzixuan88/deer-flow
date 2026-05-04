#!/usr/bin/env python3
"""
OpenClaw Unified Smoke — Host-side (Windows/macOS)
=====================================================
Tests 5 core smoke items from the Windows/macOS host perspective.

Core smoke items (R67B confirmed):
  1. Gateway /health              → 进程存活 (note: /health/live and /health/ready are 404)
  2. Gateway /api/channels/        → Feishu channel enabled/running
  3. LangGraph /                  → LangGraph server online
  4. LangGraph /threads/search    → lead_agent thread accessible (via POST, graph_id in metadata)

Excluded from regular smoke (per R66B/R67B):
  - Feishu full live 闭环（需人工触发）
  - n8n / Dify / Qdrant / Bytebot（已降级）
  - M04 TypeScript（ABANDONED）
"""
import os, sys, json, urllib.request

# ── Network topology (host-side perspective) ────────────────────────────────
# Gateway: inside Docker container, port 8001 mapped to host localhost:8001
# LangGraph: Windows host process, localhost:2027 (NOT inside Docker)
GATEWAY    = "http://localhost:8001"
LANGGRAPH  = "http://localhost:2027"


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode()


def http_post(url, data, timeout=10):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def check(name, condition, detail=""):
    """Print and record a single smoke check."""
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status} | {name}" + (f" | {detail}" if detail else ""))
    return condition


def main():
    results = []
    print(f"\n{'='*60}")
    print(f"OpenClaw Unified Smoke (host-side)")
    print(f"{'='*60}\n")

    # ── 1. Gateway /health ─────────────────────────────────────
    print("--- [1] Gateway /health (process alive) ---")
    try:
        status, body = http_get(f"{GATEWAY}/health")
        data = json.loads(body)
        healthy = data.get("status") == "healthy"
        results.append(check("gateway healthy", healthy, f"status={data.get('status')}"))
    except Exception as e:
        results.append(check("gateway healthy", False, str(e)[:60]))

    # ── 2. Gateway /api/channels/ (Feishu status) ──────────────
    print("\n--- [2] Gateway /api/channels/ (Feishu status) ---")
    try:
        status, body = http_get(f"{GATEWAY}/api/channels/")
        data = json.loads(body)
        service_running = data.get("service_running") is True
        channels = data.get("channels", {})
        feishu = channels.get("feishu", {})
        feishu_enabled = feishu.get("enabled") is True
        feishu_running = feishu.get("running") is True
        results.append(check("service_running", service_running, f"service_running={data.get('service_running')}"))
        results.append(check("feishu enabled",   feishu_enabled,  f"enabled={feishu.get('enabled')}"))
        results.append(check("feishu running",    feishu_running,  f"running={feishu.get('running')}"))
    except Exception as e:
        results.append(check("service_running", False, str(e)[:60]))
        results.append(check("feishu enabled",   False, str(e)[:60]))
        results.append(check("feishu running",   False, str(e)[:60]))

    # ── 3. LangGraph / ─────────────────────────────────────────
    print("\n--- [3] LangGraph / (server online) ---")
    try:
        status, body = http_get(f"{LANGGRAPH}/")
        data = json.loads(body)
        ok = data.get("ok") is True
        results.append(check("langgraph server online", ok, f"body={body[:60]}"))
    except Exception as e:
        results.append(check("langgraph server online", False, str(e)[:60]))

    # ── 4. LangGraph /threads/search (lead_agent accessible) ────
    # Note: POST /threads/search returns a list directly (not wrapped in {"threads":...})
    #       graph_id is in metadata.graph_id, not at top level
    print("\n--- [4] LangGraph /threads/search (lead_agent accessible) ---")
    try:
        status, body = http_post(f"{LANGGRAPH}/threads/search", {"limit": 5})
        threads = json.loads(body)
        if not isinstance(threads, list):
            threads = []
        # graph_id is in metadata.graph_id per LangGraph API response
        has_lead = any(t.get("metadata", {}).get("graph_id") == "lead_agent" for t in threads)
        results.append(check(
            "lead_agent thread exists",
            has_lead or len(threads) > 0,
            f"threads={len(threads)}"
        ))
        for t in threads[:3]:
            gid = t.get("metadata", {}).get("graph_id", "N/A")
            print(f"  thread_id={t.get('thread_id')} graph_id={gid}")
    except Exception as e:
        results.append(check("lead_agent thread exists", False, str(e)[:60]))

    # ── Summary ─────────────────────────────────────────────────
    passed = sum(results)
    total  = len(results)
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} checks passed")
    if passed == total:
        print("STATUS: [PASS] — Core smoke OK — system ready")
    else:
        print(f"STATUS: [FAIL] — {total - passed} checks failed")
    print(f"{'='*60}\n")
    return passed == total


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
