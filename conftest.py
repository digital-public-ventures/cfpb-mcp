from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repository root is importable in all pytest import modes.
# Tests import `server.py` as a top-level module.
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
