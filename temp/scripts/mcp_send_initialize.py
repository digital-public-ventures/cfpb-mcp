import json
import sys

# mcp-remote's STDIO transport expects newline-delimited JSON-RPC messages.
msg = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "local-test", "version": "0.0"},
    },
}

sys.stdout.write(json.dumps(msg, separators=(",", ":")) + "\n")
sys.stdout.flush()
