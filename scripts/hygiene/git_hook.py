"""
Git hook / hygiene checks for Capim repos.

Modes:
  - pre-commit: blocks repo bloat (scratch, outputs, temp artifacts)
  - commit-msg: enforces promotion marker when stable SQL files changed
  - ci: checks changed files between base..HEAD (used by GitHub Actions)

No external dependencies (stdlib only).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


def _run_git(args: Sequence[str]) -> str:
    out = subprocess.check_output(["git", *args], stderr=subprocess.STDOUT)
    return out.decode("utf-8", errors="replace").strip()


def repo_root() -> Path:
    return Path(_run_git(["rev-parse", "--show-toplevel"]))


def staged_files() -> List[str]:
    # Added/Copied/Modified/Renamed only
    out = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def changed_files_between(base_ref: str) -> List[str]:
    # In CI we compare base_ref..HEAD. base_ref can be a SHA or remote ref.
    out = _run_git(["diff", "--name-only", f"{base_ref}...HEAD"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def _is_forbidden_path(p: str) -> str | None:
    norm = p.replace("\\", "/")

    forbidden_prefixes = [
        "_scratch/",
        "outputs/",
        "eda/outputs/",
    ]
    for pref in forbidden_prefixes:
        if norm.startswith(pref):
            return f"Arquivo transitório em `{pref}`"

    # Common transient patterns
    if "/__pycache__/" in norm:
        return "Diretório __pycache__ não deve ser commitado"
    if norm.endswith(".pyc"):
        return "Arquivo .pyc não deve ser commitado"
    if norm.endswith("_temp.py") or norm.endswith("_debug.py"):
        return "Script temporário (_temp/_debug) não deve ser commitado"
    if norm.endswith("_temp.csv") or norm.endswith("_debug.csv"):
        return "CSV temporário (_temp/_debug) não deve ser commitado"
    if norm.endswith("_debug.png") or norm.endswith("_temp.png"):
        return "Imagem temporária (_temp/_debug) não deve ser commitada"

    # Query auto-results
    if re.search(r"^queries/.+/_results\.csv$", norm):
        return "Resultado auto-gerado de query (_results.csv) não deve ser commitado"

    return None


def _scratchpad_too_large(p: str, limit_lines: int) -> str | None:
    norm = p.replace("\\", "/")
    if not norm.endswith("scratchpad.sql"):
        return None

    abs_path = repo_root() / norm
    if not abs_path.exists():
        return None

    try:
        # Rough line count. (Scratchpads should be minimal before commit.)
        lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None

    if len(lines) > limit_lines:
        return f"scratchpad.sql inchado ({len(lines)} linhas > {limit_lines}). Migre blocos estáveis e limpe o scratchpad."
    return None


def _needs_promotion_marker(files: Iterable[str]) -> bool:
    for p in files:
        norm = p.replace("\\", "/")
        if norm.endswith(".sql") and (
            norm.startswith("queries/audit/")
            or norm.startswith("queries/studies/")
            or norm.startswith("queries/views/")
        ):
            return True
    return False


def _has_promotion_marker(msg: str) -> bool:
    # Accept either explicit approval or a reference.
    patterns = [
        r"(?im)^\s*PROMOTE-APPROVED\s*:\s*(yes|true|ok)\s*$",
        r"(?im)^\s*PROMOTE-REF\s*:\s*.+$",
    ]
    return any(re.search(pat, msg) for pat in patterns)


def check_bloat(files: List[str], *, scratchpad_line_limit: int) -> int:
    errors: List[str] = []

    for p in files:
        why = _is_forbidden_path(p)
        if why:
            errors.append(f"- `{p}`: {why}")
            continue
        sp = _scratchpad_too_large(p, scratchpad_line_limit)
        if sp:
            errors.append(f"- `{p}`: {sp}")

    if errors:
        print("[ERROR] Hygiene check falhou. Remova/mova artefatos transitorios antes de commitar:\n")
        print("\n".join(errors))
        print(
            "\nDica: use `_scratch/` para scripts temporários (gitignored) e mantenha scratchpads mínimos."
        )
        return 1

    return 0


def check_promotion_marker(files: List[str], commit_msg_path: Path) -> int:
    if not _needs_promotion_marker(files):
        return 0

    msg = commit_msg_path.read_text(encoding="utf-8", errors="replace")
    if _has_promotion_marker(msg):
        return 0

    print("[ERROR] Promotion check falhou: este commit altera SQL estavel em `queries/{audit,studies,views}/`.")
    print("Inclua um marcador explícito de aprovação no commit message, por exemplo:\n")
    print("  PROMOTE-APPROVED: yes")
    print("ou")
    print("  PROMOTE-REF: SESSION_NOTES/2026-02-12 (aprovado por Pedro)")
    print("\nIsso operacionaliza a regra: promoção só com aprovação explícita.")
    return 1


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    p_pre = sub.add_parser("pre-commit")
    p_pre.add_argument("--scratchpad-line-limit", type=int, default=int(os.getenv("SCRATCHPAD_LINE_LIMIT", "800")))

    p_msg = sub.add_parser("commit-msg")
    p_msg.add_argument("commit_msg_file")

    p_ci = sub.add_parser("ci")
    p_ci.add_argument("--base", required=True, help="Base ref/sha to diff against (base...HEAD).")
    p_ci.add_argument("--scratchpad-line-limit", type=int, default=int(os.getenv("SCRATCHPAD_LINE_LIMIT", "800")))
    p_ci.add_argument("--skip-promotion-marker", action="store_true", help="CI does not enforce commit message marker.")

    args = parser.parse_args(list(argv))

    if args.mode == "pre-commit":
        return check_bloat(staged_files(), scratchpad_line_limit=args.scratchpad_line_limit)

    if args.mode == "commit-msg":
        files = staged_files()
        return check_promotion_marker(files, Path(args.commit_msg_file))

    if args.mode == "ci":
        files = changed_files_between(args.base)
        code = check_bloat(files, scratchpad_line_limit=args.scratchpad_line_limit)
        # Promotion marker can't be reliably enforced in CI without extra conventions.
        return code

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

