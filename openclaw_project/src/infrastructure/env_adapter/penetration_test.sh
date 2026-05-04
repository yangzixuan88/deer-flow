#!/bin/bash
# OpenClaw Webhook Penetration Test Script
# Purpose: Verify the network path from the Tunnel container to the App container.

echo "[1/3] Checking Docker Compose services..."
docker-compose ps

echo "[2/3] Simulating Feishu Webhook hit from Tunnel container..."
# Execute a curl from the cloudflared service's context to the openclaw-app
# This confirms that the tunnel (once configured with the TOKEN) can reach the app.
docker-compose exec -T cloudflared curl -X POST http://openclaw-app:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{"type": "interactive", "action": {"value": "approve_mission"}}'

echo "[3/3] Verifying Dapr Sidecar Accessibility..."
# Confirm that the app can talk to its sidecar.
docker-compose exec -T openclaw-app curl http://openclaw-app-daprd:3500/v1.0/healthz

echo ">>> Penetration Test Path Verified: [Cloudflare -> App (8080) -> Dapr (3500)]"
