#!/usr/bin/env bash
set -euo pipefail

npx wrangler --config ts-mcp/wrangler.toml versions upload
