#!/usr/bin/env python3
"""
Create a lightweight repository snapshot for Claude Code context.

Usage:
  python scripts/repo_snapshot.py [path]

It prints key project files, detected stack hints, and a compact tree.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

IMPORTANT_FILES = {
    "package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json",
    "pyproject.toml", "requirements.txt", "poetry.lock",
    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "pom.xml", "build.gradle", "settings.gradle",
    "Gemfile", "composer.json",
    "Dockerfile", "docker-compose.yml",
    "Makefile", "README.md",
    "tsconfig.json", "vite.config.ts", "next.config.js",
}

IGNORE_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", ".venv", "venv",
    "__pycache__", "target", ".pytest_cache", ".turbo", ".cache"
}

def compact_tree(root: Path, max_depth: int = 3, max_entries: int = 200) -> list[str]:
    lines: list[str] = []
    count = 0

    def walk(path: Path, prefix: str = "", depth: int = 0) -> None:
        nonlocal count
        if depth > max_depth or count >= max_entries:
            return
        try:
            entries = sorted(
                [p for p in path.iterdir() if p.name not in IGNORE_DIRS],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except PermissionError:
            return
        for entry in entries:
            if count >= max_entries:
                lines.append(prefix + "...")
                return
            lines.append(prefix + ("└── " if entry == entries[-1] else "├── ") + entry.name)
            count += 1
            if entry.is_dir():
                extension = "    " if entry == entries[-1] else "│   "
                walk(entry, prefix + extension, depth + 1)

    walk(root)
    return lines

def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not root.exists():
        print(f"Path does not exist: {root}", file=sys.stderr)
        return 1

    print(f"# Repository Snapshot: {root.name}\n")

    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        current = Path(dirpath)
        for filename in filenames:
            rel = current.joinpath(filename).relative_to(root)
            if filename in IMPORTANT_FILES:
                found.append(str(rel))
    print("## Important files")
    for item in sorted(found):
        print(f"- {item}")
    if not found:
        print("- None detected")

    print("\n## Tree")
    for line in compact_tree(root):
        print(line)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
