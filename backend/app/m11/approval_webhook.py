"""
approval_webhook.py
==================
R198: Feishu approval callback receiver.

Receives interactive card button-click callbacks from Feishu when a manager
clicks [批准/否决/加入观察池] on an upgrade_center approval card.

MINIMUM CLOSED LOOP (Round 198):
  Feishu card sent via lark-cli
    → manager clicks button in Feishu
    → Feishu POSTs callback to this webhook
    → governance_bridge.record_outcome('upgrade_center_approval_result')
    → governance_state.json updated
    → DemandSampler can see result in next cycle

Feishu Card Callback format:
  POST /approval_callback (Content-Type: application/json)
  {
    "action": {
      "value": "approve" | "observe" | "reject",
      "key": "approval_action_<candidate_id>"
    },
    "open_id": "ou_xxxxx",
    "token": "xxxxx"
  }

Usage:
  python -m app.m11.approval_webhook [--port 8088]
  (run from deerflow root: E:/OpenClaw-Base/deerflow/backend/)
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import threading

# Path resolution
_backend_dir = Path(__file__).parent.parent  # deerflow/backend
PROJECT_ROOT = _backend_dir.parent
sys.path.insert(0, str(_backend_dir))

from app.m11.governance_bridge import governance_bridge

# ---------------------------------------------------------------------------
# Governance state helpers
# ---------------------------------------------------------------------------

def write_approval_result(
    candidate_id: str,
    result: str,          # 'approved' | 'rejected' | 'observe'
    open_id: str,
    executed_at: str,
) -> bool:
    """
    Write an upgrade_center_approval_result outcome to governance_state.json
    via governance_bridge.record_outcome().
    Returns True on success.
    """
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_write_approval_result_async(
            candidate_id, result, open_id, executed_at
        ))
        return True
    except Exception as e:
        print(f"[ApprovalWebhook] Failed to write result: {e}", flush=True)
        return False


async def _write_approval_result_async(
    candidate_id: str,
    result: str,
    open_id: str,
    executed_at: str,
) -> None:
    """Async wrapper around governance_bridge.record_outcome()."""
    await governance_bridge.record_outcome(
        outcome_type='upgrade_center_approval_result',
        actual_result=1.0 if result == 'approved' else 0.0,
        predicted_result=0.9,
        context={
            'candidate_id': candidate_id,
            'result': result,          # approved / rejected / observe
            'approver_open_id': open_id,
            'executed_at': executed_at,
            'source': 'feishu_approval',
        },
    )
    print(f"[ApprovalWebhook] Recorded approval_result for {candidate_id}: {result}", flush=True)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class ApprovalCallbackHandler(BaseHTTPRequestHandler):
    """Receives Feishu interactive card callbacks."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging, use flush for immediate output."""
        print(f"[ApprovalWebhook] {format % args}", flush=True)

    def do_GET(self):
        """Health check: GET /approval_callback returns 200."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok', 'service': 'approval_webhook'}).encode())

    def do_POST(self):
        """
        Receive Feishu card callback.

        Feishu sends POST with JSON body like:
        {
          "action": {
            "value": "approve",      // button value
            "key": "approval_action_<candidate_id>"
          },
          "open_id": "ou_xxx",
          "token": "xxx"
        }
        """
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}

        action = payload.get('action', {})
        action_value = action.get('value', '')
        action_key = action.get('key', '')
        open_id = payload.get('open_id', '')

        # Parse candidate_id from action_key (format: "approval_action_<candidate_id>")
        candidate_id = action_key.replace('approval_action_', '') if action_key else ''
        if not candidate_id:
            candidate_id = payload.get('candidate_id', 'unknown')

        executed_at = payload.get('executed_at', '')

        # Map Feishu button values to our result labels
        result_map = {
            'approve': 'approved',
            '批准': 'approved',
            'reject': 'rejected',
            '否决': 'rejected',
            'observe': 'observe',
            '加入观察池': 'observe',
        }
        result = result_map.get(action_value, action_value if action_value else 'unknown')

        print(f"[ApprovalWebhook] Callback: candidate={candidate_id}, result={result}, "
              f"open_id={open_id}, raw_value={action_value}", flush=True)

        # Write to governance_state
        success = write_approval_result(candidate_id, result, open_id, executed_at or '')

        # Respond to Feishu
        self.send_response(200 if success else 500)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {'status': 'ok' if success else 'error'}
        self.wfile.write(json.dumps(response).encode())


# ---------------------------------------------------------------------------
# Standalone server
# ---------------------------------------------------------------------------

def run_server(port: int = 8088) -> None:
    """Run the approval webhook HTTP server."""
    server = HTTPServer(('0.0.0.0', port), ApprovalCallbackHandler)
    print(f"[ApprovalWebhook] Listening on http://0.0.0.0:{port}/approval_callback", flush=True)
    print("[ApprovalWebhook] Configure this URL in Feishu Card Bot webhook settings.", flush=True)
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Feishu Approval Webhook Receiver')
    parser.add_argument('--port', type=int, default=8088, help='Port to listen on (default: 8088)')
    args = parser.parse_args()
    run_server(args.port)
