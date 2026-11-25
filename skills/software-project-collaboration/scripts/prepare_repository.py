#!/usr/bin/env python3
"""Prepare a reviewable GitHub repository; never create a remote, commit or publish. Default: preview."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from export_skill import NAME, source_files
from file_ops import checked_root, create_planned, plan_files


def repository_files(source: Path, repository: str, release_ref: str) -> dict[str, bytes]:
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9][A-Za-z0-9._-]{0,99}", repository):
        raise ValueError("repository must be a GitHub OWNER/REPO without a URL or shell syntax")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", release_ref) or any(
            bad in release_ref for bad in ("..", "//")) or release_ref.endswith(("/", ".", ".lock")):
        raise ValueError("release-ref must be a simple Git tag or full commit SHA")
    core = source_files(source)
    text = core["SKILL.md"].decode("utf-8")
    match = re.search(r'^  version: "([0-9]+\.[0-9]+\.[0-9]+)"$', text, re.M)
    if not match:
        raise ValueError("Expected metadata.version in the maintained skill")
    version = match.group(1)
    files = {f"skills/{NAME}/{relative}": data for relative, data in core.items()}
    files["LICENSE"] = core["LICENSE.txt"]
    template_root = source / "assets" / "publishing"
    if template_root.is_symlink() or not template_root.is_dir():
        raise ValueError("Publishing templates are missing or symlinked")
    for path in sorted(template_root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Publishing template symlink: {path}")
        if not path.is_file() or not path.name.endswith(".template"):
            continue
        relative = path.relative_to(template_root).as_posix().removesuffix(".template")
        rendered = path.read_text(encoding="utf-8")
        for key, value in {"__REPOSITORY__": repository, "__RELEASE_REF__": release_ref,
                           "__SKILL_VERSION__": version}.items():
            rendered = rendered.replace(key, value)
        if relative in files:
            raise ValueError(f"Duplicate generated path: {relative}")
        files[relative] = rendered.encode("utf-8")
    manifest = {
        "schema_version": 1,
        "skill_name": NAME,
        "version": version,
        "proposed_repository": repository,
        "proposed_ref": release_ref,
        "claim": "Content snapshot only; does not attest publication or runtime validation.",
        "files": {relative: hashlib.sha256(data).hexdigest() for relative, data in sorted(files.items())},
    }
    files["release-manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Destination directory; conflicting content is never overwritten")
    parser.add_argument("--repository", required=True, help="Proposed GitHub OWNER/REPO; no network lookup or creation")
    parser.add_argument("--release-ref", default="v0.3.0", help="Proposed release tag or full SHA; not published by this script")
    parser.add_argument("--apply", action="store_true", help="Create absent files only after the complete plan is conflict-free")
    args = parser.parse_args()
    try:
        root = checked_root(args.root)
        source = Path(__file__).resolve().parents[1]
        files = repository_files(source, args.repository, args.release_ref)
        plan = plan_files(root, files)
        conflict = any(item["action"] == "conflict" for item in plan)
        created = create_planned(root, files, plan) if args.apply and not conflict else []
        print(json.dumps({"root": str(root), "mode": "apply" if args.apply else "preview",
                          "proposed_repository": args.repository, "proposed_ref": args.release_ref,
                          "file_count": len(files), "plan": plan, "created": created, "conflict": conflict,
                          "published": False, "note": "Review candidate, validate, and obtain any required publication authorization separately."},
                         ensure_ascii=False, indent=2))
        return 2 if conflict else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
