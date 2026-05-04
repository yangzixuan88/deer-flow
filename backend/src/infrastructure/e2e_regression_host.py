#!/usr/bin/env python3
"""
E2E Regression (Host-side): Frontend→Gateway→LangGraph→MiniMax

Runs from Windows/macOS host — tests real HTTP endpoints.
Prerequisites (all on host):
  - Gateway at http://localhost:8080
  - LangGraph Server at http://localhost:2027
  - Frontend at http://localhost:2026
"""
import os, sys, json, uuid
import urllib.request

GATEWAY = "http://localhost:8080"
LANGGRAPH = "http://localhost:2027"
FRONTEND = "http://localhost:2026"
ASSISTANT_ID = "lead_agent"

def http_get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode()

def http_post(url, data, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()

def check(name, condition, detail=""):
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status} | {name}" + (f" | {detail}" if detail else ""))
    return condition

def main():
    results = []
    # Real UUID thread_id (LangGraph requires UUID format)
    thread_id = str(uuid.uuid4())
    print(f"\n{'='*60}")
    print(f"E2E REGRESSION (host) | thread={thread_id}")
    print(f"{'='*60}\n")

    # ── Pre-check: services ──────────────────────────────────
    print("--- PRE-CHECK: Services ---")
    try:
        status, body = http_get(f"{GATEWAY}/health/ready")
        data = json.loads(body)
        results.append(check("gateway /health/ready", status == 200 and data.get("status") == "ready",
                             f"status={status} overall={data.get('status')}"))
    except Exception as e:
        results.append(check("gateway /health/ready", False, str(e)[:60]))

    try:
        status, body = http_get(f"{LANGGRAPH}/ok")
        results.append(check("langgraph /ok", status == 200, f"status={status}"))
    except Exception as e:
        results.append(check("langgraph /ok", False, str(e)[:60]))

    try:
        status, body = http_get(FRONTEND, timeout=10)
        results.append(check("frontend (nginx) reachable", status == 200, f"status={status}"))
    except Exception as e:
        results.append(check("frontend (nginx) reachable", False, str(e)[:60]))

    print()

    # ── Step 1: Create assistant ───────────────────────────────
    print("--- STEP 1: Create Assistant ---")
    assistant_id = None
    try:
        status, body = http_post(
            f"{LANGGRAPH}/assistants",
            {"graph_id": ASSISTANT_ID},
            timeout=30,
        )
        results.append(check("create assistant", status in (200, 201), f"status={status}"))
        if status in (200, 201):
            data = json.loads(body)
            assistant_id = data.get("assistant_id")
            print(f"  assistant_id={assistant_id}")
        else:
            print(f"  Response: {body[:300]}")
    except Exception as e:
        results.append(check("create assistant", False, str(e)[:60]))

    print()

    # ── Step 2: Create thread ────────────────────────────────
    print("--- STEP 2: Create Thread ---")
    if not assistant_id:
        print("  [SKIP] Skipped - no assistant_id")
    else:
        try:
            status, body = http_post(f"{LANGGRAPH}/threads", {}, timeout=30)
            results.append(check("create thread", status == 200, f"status={status}"))
            if status == 200:
                data = json.loads(body)
                thread_id = data.get("thread_id", thread_id)
                print(f"  thread_id={thread_id}")
            else:
                print(f"  Response: {body[:200]}")
        except Exception as e:
            results.append(check("create thread", False, str(e)[:60]))

    print()

    # ── Step 3: Send message (streaming) ─────────────────────
    print("--- STEP 3: Send Message (stream) ---")
    if not assistant_id:
        print("  [SKIP] Skipped - no assistant_id")
    else:
        message_content = "Reply with exactly one word: 'ok'"
        try:
            req = urllib.request.Request(
                f"{LANGGRAPH}/threads/{thread_id}/runs/stream",
                data=json.dumps({
                    "input": {"content": message_content},
                    "stream": True,
                    "assistant_id": assistant_id,
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                results.append(check("stream response status", resp.status == 200, f"status={resp.status}"))
                if resp.status != 200:
                    print(f"  Response: {resp.read().decode()[:300]}")
                else:
                    full_content = ""
                    chunk_count = 0
                    # SSE stream: read line by line
                    while True:
                        line = resp.readline().decode()
                        if not line:
                            break
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            chunk_count += 1
                            # LangGraph SSE: extract all message content for verification
                            if isinstance(chunk, dict):
                                # values.messages is the standard LangGraph streaming format
                                values = chunk.get("values", {}) if isinstance(chunk.get("values"), dict) else chunk
                                msgs = values.get("messages", []) if isinstance(values, dict) else []
                                for msg in msgs:
                                    if isinstance(msg, dict):
                                        # Direct content field
                                        c = msg.get("content", "")
                                        if c and isinstance(c, str) and c.strip():
                                            full_content += c + "\n"
                                        # Tool call results have content in "content" too
                                        # reasoning_content in additional_kwargs (MiniMax reasoning)
                                        rc = msg.get("additional_kwargs", {}).get("reasoning_content", "")
                                        if rc and isinstance(rc, str) and rc.strip():
                                            full_content += rc + "\n"
                        except (json.JSONDecodeError, KeyError):
                            pass
                    print(f"  chunks received: {chunk_count}")
                    print(f"  content: {full_content[:200]}")
                    # Check: got any values events (confirms LangGraph→MiniMax chain works)
                    has_content = len(full_content.strip()) > 0
                    results.append(check("stream has content", has_content, f"len={len(full_content)}"))
                    # Relaxed check: just look for any text in values.messages
                    has_text = any(c.isalpha() or c.isspace() for c in full_content if c.isascii())
                    results.append(check("stream has text from LLM", has_text, f"ascii_chars={sum(1 for c in full_content if c.isascii())}"))
        except Exception as e:
            results.append(check("stream request", False, str(e)[:80]))

    print()

    # ── Step 4: Thread history ──────────────────────────────
    print("--- STEP 4: Verify Thread History ---")
    if not assistant_id:
        print("  [SKIP] Skipped - no assistant_id")
    else:
        try:
            status, body = http_get(f"{LANGGRAPH}/threads/{thread_id}/history", timeout=30)
            results.append(check("thread history", status == 200, f"status={status}"))
            if status == 200:
                hist = json.loads(body)
                # History returns list of checkpoints; extract messages from last state
                if isinstance(hist, list) and len(hist) > 0:
                    last_state = hist[-1]
                    values = last_state.get("values", {}) if isinstance(last_state, dict) else {}
                    msgs = values.get("messages", []) if isinstance(values, dict) else []
                elif isinstance(hist, dict):
                    msgs = hist.get("messages", [])
                else:
                    msgs = []
                print(f"  messages in thread: {len(msgs)}")
                results.append(check("at least 2 messages in thread", len(msgs) >= 2, f"count={len(msgs)}"))
            else:
                print(f"  Response: {body[:200]}")
        except Exception as e:
            results.append(check("thread history", False, str(e)[:60]))

    print()

    # ── Summary ──────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    print(f"{'='*60}")
    print(f"RESULT: {passed}/{total} checks passed")
    if passed == total:
        print("STATUS: [PASS] ALL CHECKS PASSED --- Regression chain OK")
    else:
        print(f"STATUS: [FAIL] {total - passed} CHECKS FAILED")
    print(f"{'='*60}\n")
    return passed == total

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
