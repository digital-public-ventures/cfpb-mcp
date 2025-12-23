#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP_URL="${MCP_URL:-http://127.0.0.1:8787/mcp}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8787/health}"

cleanup() {
	if [[ -n "${WRANGLER_PID:-}" ]]; then
		kill "${WRANGLER_PID}" 2>/dev/null || true
		wait "${WRANGLER_PID}" 2>/dev/null || true
	fi
}

trap cleanup EXIT

(
	cd "${ROOT_DIR}/ts-mcp"
	npx wrangler dev --local --port 8787 --ip 127.0.0.1
) &
WRANGLER_PID=$!

for _ in {1..60}; do
	if curl -fsS "${HEALTH_URL}" >/dev/null; then
		break
	fi
	sleep 0.5
done

node "${ROOT_DIR}/ts-mcp/scripts/mcp_probe.mjs" --url "${MCP_URL}"
