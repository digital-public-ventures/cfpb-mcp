#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/jim/cfpb-mcp"
PORT="${PORT_OVERRIDE:-8000}"
REMOTE_URL="http://127.0.0.1:${PORT}/mcp/sse"

TMPBASE="${TMPDIR:-/tmp}"
UVLOG="$TMPBASE/cfpb_uvicorn_${PORT}.log"
OUTBIN="$TMPBASE/cfpb_shim_out_${PORT}.bin"
ERRTXT="$TMPBASE/cfpb_shim_err_${PORT}.txt"

rm -f "$UVLOG" "$OUTBIN" "$ERRTXT" || true

# Start uvicorn in background
"$ROOT/.venv/bin/python" -m uvicorn server:app --host 127.0.0.1 --port "$PORT" >"$UVLOG" 2>&1 &
UVPID=$!

cleanup() {
	kill "$UVPID" >/dev/null 2>&1 || true
	sleep 0.2 || true
}
trap cleanup EXIT

sleep 1

echo "== running shim against $REMOTE_URL =="
(
	"$ROOT/.venv/bin/python" "$ROOT/temp/mcp_send_initialize.py"
	sleep "${KEEP_OPEN_SECS:-2}"
) |
	REMOTE_MCP_URL="$REMOTE_URL" node "$ROOT/deployment/anthropic/mcpb/server/index.js" \
		>"$OUTBIN" 2>"$ERRTXT" || true

echo
echo "== shim stderr (tail) =="
tail -n 200 "$ERRTXT" || true

echo
echo "== shim stdout (first 800 bytes, decoded) =="
"$ROOT/.venv/bin/python" -c "p='$OUTBIN'; d=open(p,'rb').read(800); print(d.decode('utf-8','replace'))" || true

echo
echo "== uvicorn log (tail) =="
tail -n 120 "$UVLOG" || true
