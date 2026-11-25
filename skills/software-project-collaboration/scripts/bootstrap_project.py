#!/usr/bin/env python3
"""Preview or add engineering entry documents. Does not scaffold app code or run commands."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from file_ops import checked_root, create_planned, plan_files

MINIMAL = {
    "README.md": "README.md", "AGENTS.md": "AGENTS.md", "CLAUDE.md": "CLAUDE.md",
    "PROJECT.md": "docs/PROJECT.md", "STATUS.md": "docs/STATUS.md",
    "project.json": ".engineering/project.json",
}
STANDARD = {
    "architecture.md": "docs/architecture/overview.md", "testing.md": "docs/testing.md",
    "runbook.md": "docs/operations/runbook.md",
    "engineering-contract.md": "docs/engineering-contract.md",
    "release.md": "docs/operations/release.md",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Target project directory, never overwritten")
    parser.add_argument("--name", required=True, help="Human-readable project name")
    parser.add_argument("--tier", choices=("minimal", "standard"), default="minimal")
    parser.add_argument("--date", help="ISO date; default is current Asia/Shanghai date")
    parser.add_argument("--apply", action="store_true", help="Create absent files; otherwise preview only")
    args = parser.parse_args()
    try:
        if not args.name.strip() or len(args.name) > 160 or any(ord(c) < 32 for c in args.name):
            raise ValueError("Project name must be 1–160 characters without control characters")
        today = args.date or dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
        dt.date.fromisoformat(today)
        root = checked_root(args.root)
        templates = Path(__file__).resolve().parents[1] / "assets" / "bootstrap"
        selected = dict(MINIMAL)
        if args.tier == "standard":
            selected.update(STANDARD)
        files = {}
        for template, destination in selected.items():
            text = (templates / template).read_text(encoding="utf-8")
            if template == "project.json":
                config = json.loads(text)
                config["project_name"] = args.name
                text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
            else:
                text = text.replace("{{PROJECT_NAME}}", args.name).replace("{{DATE}}", today)
            files[destination] = text.encode("utf-8")
        plan = plan_files(root, files)
        conflict = any(x["action"] == "conflict" for x in plan)
        created = create_planned(root, files, plan) if args.apply and not conflict else []
        print(json.dumps({"root": str(root), "mode": "apply" if args.apply else "preview",
                          "plan": plan, "created": created, "conflict": conflict,
                          "note": "No app code, dependencies, tests, Git state, or permissions changed."},
                         ensure_ascii=False, indent=2))
        return 2 if conflict else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "note": "No existing file was overwritten."}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
