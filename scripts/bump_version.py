#!/usr/bin/env python3
"""Bump the Bangtrix Toolkit version in lockstep across __init__.py and
pyproject.toml, then print the next git commands to run.

Usage:
    python scripts/bump_version.py <new-version>

Examples:
    python scripts/bump_version.py 1.3.7
    python scripts/bump_version.py 1.4.0

What it does:
  1. Validates the new version against PEP 440 (X.Y.Z with optional
     pre-release / build suffix).
  2. Updates ``pyproject.toml``'s ``[project].version``.
  3. Updates ``__init__.py``'s ``__version__``.
  4. Prints (does not run) the git add/commit/push commands for the
     release.

Why this exists: the publish workflow at
``.github/workflows/publish_action.yml`` only fires when
``pyproject.toml`` changes on ``main``. The two version strings must
agree — drift between them surfaces as a stale ``__version__`` in the
loaded module while the registry reports the new one, which is the
exact bug we hit before this script existed.

It does NOT touch git tags — those are derived from ``pyproject.toml``
by the registry, so a tag here would only be cosmetic noise.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT_PY = REPO_ROOT / "__init__.py"

# PEP 440 — matches what `comfy-cli` and the registry accept.
# Examples: 1.2.3, 1.2.3a1, 1.2.3b2, 1.2.3rc1, 1.2.3.post1
PEP440 = re.compile(
    r"^\d+(\.\d+){0,2}"
    r"(\.(a|b|rc)\d+)?"
    r"(\.post\d+)?"
    r"(\.dev\d+)?$"
)


def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def bump_file(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    text = path.read_text()
    new_text, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        fail(f"could not find version line in {path} (pattern: {pattern.pattern!r})")
    if new_text == text:
        fail(f"version unchanged in {path} — was it already {replacement!r}?")
    path.write_text(new_text)
    print(f"  updated {path.relative_to(REPO_ROOT)}")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    new_version = sys.argv[1].strip()
    if not PEP440.match(new_version):
        fail(f"{new_version!r} is not PEP 440 (e.g. 1.2.3, 1.2.3rc1)")

    pyproject_pattern = re.compile(r'(?m)^version\s*=\s*"[^"]+"$')
    init_pattern = re.compile(r'(?m)^__version__\s*=\s*"[^"]+"$')

    print(f"bumping to {new_version}:")
    bump_file(PYPROJECT, pyproject_pattern, f'version = "{new_version}"')
    bump_file(INIT_PY, init_pattern, f'__version__ = "{new_version}"')

    print()
    print("next steps:")
    print(f"  git add pyproject.toml __init__.py")
    print(f'  git commit -m "Release {new_version}"')
    print(f"  git push origin main")
    print()
    print("publish workflow will run automatically on push to main.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())