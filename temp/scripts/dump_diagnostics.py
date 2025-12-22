from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def _fmt_cmd(cmd: list[str]) -> str:
    return " ".join(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Auto-fix/format with Ruff, then write Ruff and Pyright (Pylance engine) diagnostics "
            "to a txt file under temp/output."
        )
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="File or directory to check (default: .)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output .txt path (default: temp/output/diagnostics_YYYYMMDD_HHMMSS.txt)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    target = Path(args.target)
    target_path = (target if target.is_absolute() else (repo_root / target)).resolve()

    if not target_path.exists():
        print(f"Target not found: {target_path}", file=sys.stderr)
        return 2

    out_dir = repo_root / "temp" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.out is None:
        stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
        safe_target = str(target_path.relative_to(repo_root) if target_path.is_relative_to(repo_root) else target_path)
        safe_target = safe_target.replace("/", "__").replace(" ", "_")
        out_path = out_dir / f"diagnostics_{safe_target}_{stamp}.txt"
    else:
        out_path = (args.out if args.out.is_absolute() else (repo_root / args.out)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

    sections: list[str] = []
    sections.append(f"timestamp_utc: {dt.datetime.now(dt.UTC).isoformat()}\n")
    sections.append(f"python: {sys.executable}\n")
    sections.append(f"target: {target_path}\n\n")

    # Ruff
    ruff = shutil.which("ruff")
    if ruff:
        fix_cmd = ["ruff", "check", "--fix", str(target_path)]
        code, stdout, stderr = _run(fix_cmd, cwd=repo_root)
        sections.append("=== ruff check --fix ===\n")
        sections.append(f"cmd: {_fmt_cmd(fix_cmd)}\n")
        sections.append(f"exit_code: {code}\n")
        if stderr.strip():
            sections.append("--- stderr ---\n")
            sections.append(stderr)
            if not stderr.endswith("\n"):
                sections.append("\n")
        sections.append("--- stdout ---\n")
        sections.append(stdout or "(no output)\n")
        if stdout and not stdout.endswith("\n"):
            sections.append("\n")
        sections.append("\n")

        fmt_cmd = ["ruff", "format", str(target_path)]
        code, stdout, stderr = _run(fmt_cmd, cwd=repo_root)
        sections.append("=== ruff format ===\n")
        sections.append(f"cmd: {_fmt_cmd(fmt_cmd)}\n")
        sections.append(f"exit_code: {code}\n")
        if stderr.strip():
            sections.append("--- stderr ---\n")
            sections.append(stderr)
            if not stderr.endswith("\n"):
                sections.append("\n")
        sections.append("--- stdout ---\n")
        sections.append(stdout or "(no output)\n")
        if stdout and not stdout.endswith("\n"):
            sections.append("\n")
        sections.append("\n")

        check_cmd = ["ruff", "check", str(target_path)]
        code, stdout, stderr = _run(check_cmd, cwd=repo_root)
        sections.append("=== ruff check ===\n")
        sections.append(f"cmd: {_fmt_cmd(check_cmd)}\n")
        sections.append(f"exit_code: {code}\n")
        if stderr.strip():
            sections.append("--- stderr ---\n")
            sections.append(stderr)
            if not stderr.endswith("\n"):
                sections.append("\n")
        sections.append("--- stdout ---\n")
        sections.append(stdout or "(no output)\n")
        if stdout and not stdout.endswith("\n"):
            sections.append("\n")
        sections.append("\n")
    else:
        sections.append("=== ruff ===\n")
        sections.append("ruff not found on PATH; skipping.\n\n")

    # Pylance uses Pyright engine; try to run Pyright if available.
    # (We can't directly query VS Code Pylance diagnostics from a standalone script.)
    pyright_cmd: list[str] | None = None
    if shutil.which("pyright"):
        pyright_cmd = ["pyright"]
    elif shutil.which("basedpyright"):
        pyright_cmd = ["basedpyright"]
    else:
        # Some environments have the Python package `pyright` but no shim.
        pyright_cmd = [sys.executable, "-m", "pyright"]

    code, stdout, stderr = _run([*pyright_cmd, str(target_path)], cwd=repo_root)
    sections.append("=== pyright (pylance engine) ===\n")
    sections.append(f"cmd: {_fmt_cmd([*pyright_cmd, str(target_path)])}\n")
    sections.append(f"exit_code: {code}\n")
    if stderr.strip():
        sections.append("--- stderr ---\n")
        sections.append(stderr)
        if not stderr.endswith("\n"):
            sections.append("\n")
    sections.append("--- stdout ---\n")
    if stdout.strip():
        sections.append(stdout)
        if not stdout.endswith("\n"):
            sections.append("\n")
    else:
        # If pyright isn't installed, `python -m pyright` will typically explain on stderr.
        sections.append("(no output)\n")
    sections.append("\n")

    out_path.write_text("".join(sections), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
