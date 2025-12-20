#!/usr/bin/env bash
set -euo pipefail

# Checks whether Claude Desktop is still using a legacy mcpServers entry
# that launches `npx mcp-remote ...` instead of the installed .mcpb shim.

say() { printf "\n## %s\n" "$1"; }

say "Environment"
echo "whoami: $(whoami)"
echo "HOME: $HOME"
echo "pwd: $(pwd)"
echo "bash: $BASH_VERSION"
echo "grep: $(command -v grep || true)"

default_cfg="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

say "Locate claude_desktop_config.json (common path)"
if [[ -f "$default_cfg" ]]; then
	echo "FOUND: $default_cfg"
else
	echo "NOT FOUND: $default_cfg"
fi

say "Locate claude_desktop_config.json (Spotlight by filename)"
if command -v mdfind >/dev/null 2>&1; then
	# IMPORTANT: Use a filename query. A bare string query matches file CONTENTS too,
	# which can produce tons of false positives (e.g., VS Code chat caches).
	mdfind 'kMDItemFSName == "claude_desktop_config.json"' 2>/dev/null | cat || true
else
	echo "mdfind not available"
fi

say "Locate claude_desktop_config.json (find fallback under Claude App Support)"
claude_support_dir="$HOME/Library/Application Support/Claude"
if [[ -d "$claude_support_dir" ]]; then
	find "$claude_support_dir" -maxdepth 6 -name "claude_desktop_config.json" 2>/dev/null | cat || true
else
	echo "NOT FOUND: $claude_support_dir"
fi

say "Scan configs for legacy 'npx mcp-remote' usage"

# Build a unique list of candidate config paths, restricted to Claude's support dir.
mapfile -t cfgs < <(
	{
		[[ -f "$default_cfg" ]] && echo "$default_cfg" || true
		if command -v mdfind >/dev/null 2>&1; then
			mdfind 'kMDItemFSName == "claude_desktop_config.json"' 2>/dev/null | /usr/bin/grep -F "/Library/Application Support/Claude/" || true
		fi
		if [[ -d "$claude_support_dir" ]]; then
			find "$claude_support_dir" -maxdepth 6 -name "claude_desktop_config.json" 2>/dev/null || true
		fi
	} | /usr/bin/sort -u
)

if [[ ${#cfgs[@]} -eq 0 ]]; then
	echo "No claude_desktop_config.json files found under: $claude_support_dir"
	echo "If Claude is using a different config file name/location, we can search for it next."
else
	for cfg in "${cfgs[@]}"; do
		echo
		echo "---"
		echo "FILE: $cfg"
		echo "---"

		echo "[match] cfpb-complaints:"
		/usr/bin/grep -nF "cfpb-complaints" "$cfg" | cat || true

		echo "[match] mcp-remote:"
		/usr/bin/grep -nF "mcp-remote" "$cfg" | cat || true

		echo "[match] command npx:"
		/usr/bin/grep -nF '"command": "npx"' "$cfg" | cat || true
	done
fi

say "Scan all Claude JSON files for MCP legacy patterns"
if [[ -d "$claude_support_dir" ]]; then
	# Sometimes the MCP server config is stored in a differently named JSON file.
	# This scans ONLY within Claude's support dir.
	while IFS= read -r -d '' f; do
		if /usr/bin/grep -qE '"mcpServers"|cfpb-complaints|mcp-remote|"command"\s*:\s*"npx"' "$f"; then
			echo
			echo "---"
			echo "FILE: $f"
			echo "---"
			/usr/bin/grep -nE '"mcpServers"|cfpb-complaints|mcp-remote|"command"\s*:\s*"npx"' "$f" | cat || true
		fi
	done < <(find "$claude_support_dir" -maxdepth 6 -type f -name "*.json" -print0 2>/dev/null)
else
	echo "NOT FOUND: $claude_support_dir"
fi

say "List Claude MCP logs (CFPB-related)"
log_dir="$HOME/Library/Logs/Claude"
if [[ -d "$log_dir" ]]; then
	ls -1 "$log_dir" | /usr/bin/grep -E "mcp-server|cfpb|CFPB" | cat || true
else
	echo "NOT FOUND: $log_dir"
fi

say "Tail CFPB logs (last 120 lines each)"
for lf in "$log_dir/mcp-server-cfpb-complaints.log" "$log_dir/mcp-server-CFPB Consumer Complaints.log"; do
	echo
	if [[ -f "$lf" ]]; then
		echo "--- TAIL: $lf ---"
		tail -n 120 "$lf" | cat
	else
		echo "MISSING: $lf"
	fi
done

say "Verdict (log-based)"
legacy_log="$log_dir/mcp-server-cfpb-complaints.log"
if [[ -f "$legacy_log" ]]; then
	# Avoid false positives from old historical runs by focusing on recent output.
	if tail -n 500 "$legacy_log" | /usr/bin/grep -qF "/.npm/_npx/"; then
		echo "Legacy runtime signature seen in the last 500 lines of: $legacy_log"
		echo "This likely means Claude is currently launching 'npx mcp-remote' (legacy/manual config) for a server named 'cfpb-complaints'."
	elif /usr/bin/grep -qF "/.npm/_npx/" "$legacy_log"; then
		echo "Legacy runtime signature exists somewhere in: $legacy_log"
		echo "But it is NOT present in the last 500 lines, so it may be historical noise."
	else
		echo "No '/.npm/_npx/' signature found in $legacy_log."
	fi
else
	echo "MISSING: $legacy_log"
fi

say "How to interpret"

echo "- If the config grep shows a block like:"
echo "    \"cfpb-complaints\": { \"command\": \"npx\", \"args\": [\"-y\",\"mcp-remote\", ...] }"
echo "  ...then the legacy entry is still present."
echo
echo "- In logs:"
echo "  - If you see: \"Using MCP server command: .../npx -y mcp-remote ...\" => legacy/manual config is running."
echo "  - If you see lines starting with: \"[CFPB MCPB]\" => the .mcpb shim is running."

say "Tail MCPB shim log (file-based)"
tmpdir_py="$(python3 -c 'import tempfile; print(tempfile.gettempdir())' 2>/dev/null || true)"
shim_log="${tmpdir_py}/cfpb-mcpb.log"

# Also check the installed extension directory (deterministic log path when CFPB_MCPB_LOG_FILE is set).
ext_root="$HOME/Library/Application Support/Claude/Claude Extensions/local.mcpb.digital-public-ventures.cfpb-complaints"
ext_log="$ext_root/cfpb-mcpb.log"

echo "tempdir: ${tmpdir_py:-<unknown>}"
echo "expected shim log: $shim_log"
if [[ -n "${tmpdir_py:-}" && -f "$shim_log" ]]; then

	# Show file metadata then tail.
	ls -la "$shim_log" | cat
	echo
	tail -n 200 "$shim_log" | cat
else
	echo "No shim log found at: $shim_log"
fi

echo
echo "installed extension log: $ext_log"
if [[ -f "$ext_log" ]]; then
	ls -la "$ext_log" | cat
	echo
	tail -n 200 "$ext_log" | cat
else
	echo "No extension-root shim log found at: $ext_log"
fi
