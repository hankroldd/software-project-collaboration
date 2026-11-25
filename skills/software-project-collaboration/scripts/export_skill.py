#!/usr/bin/env python3
"""Export a create-only snapshot for Codex, Claude Code and OpenCode. Default: preview."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from file_ops import checked_root, create_planned, plan_files

NAME = "software-project-collaboration"
DIRECTORIES = ("agents", "references", "scripts", "assets")


def portable_interface(data: bytes) -> bytes:
    """Keep display metadata only; host-managed policy is not a portable permission."""
    lines = data.decode("utf-8").splitlines()
    selected: list[str] = []
    inside = False
    for line in lines:
        if line == "interface:":
            inside = True
            selected.append(line)
        elif inside:
            if line and not line[0].isspace() and not line.startswith("#"):
                break
            selected.append(line)
    if not selected or not any(line.startswith("  display_name:") for line in selected):
        raise ValueError("Expected a simple interface mapping in agents/openai.yaml")
    return ("\n".join(selected).rstrip() + "\n").encode("utf-8")


def source_files(source: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for name in ("SKILL.md", "LICENSE.txt"):
        path = source / name
        if path.is_symlink():
            raise ValueError(f"Source symlinks are not exported: {path}")
        result[name] = path.read_bytes()
    for directory in DIRECTORIES:
        directory_path = source / directory
        if directory_path.is_symlink():
            raise ValueError(f"Source directory symlinks are not exported: {directory_path}")
        for p in sorted(directory_path.rglob("*")):
            if p.is_symlink():
                raise ValueError(f"Source symlinks are not exported: {p}")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                relative = p.relative_to(source).as_posix()
                data = p.read_bytes()
                result[relative] = portable_interface(data) if relative == "agents/openai.yaml" else data
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Target project root")
    parser.add_argument("--target", choices=("codex", "claude", "opencode", "both", "all"), default="all",
                        help="codex/opencode share .agents; both/all also create .claude")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        root = checked_root(args.root)
        source = Path(__file__).resolve().parents[1]
        originals = source_files(source)
        prefixes = []
        if args.target in ("codex", "opencode", "both", "all"):
            prefixes.append(f".agents/skills/{NAME}")
        if args.target in ("claude", "both", "all"):
            prefixes.append(f".claude/skills/{NAME}")
        files = {f"{prefix}/{rel}": data for prefix in prefixes for rel, data in originals.items()}
        # Two destinations are planned before any write, so a known conflict prevents the whole export.
        plan = plan_files(root, files)
        conflict = any(x["action"] == "conflict" for x in plan)
        created = create_planned(root, files, plan) if args.apply and not conflict else []
        print(json.dumps({"root": str(root), "mode": "apply" if args.apply else "preview",
                          "target": args.target, "plan": plan, "created": created,
                          "conflict": conflict, "note": "Create-only snapshot, not a package manager. No CLI lock, hooks, permissions, AGENTS.md or CLAUDE.md changed."},
                         ensure_ascii=False, indent=2))
        return 2 if conflict else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
