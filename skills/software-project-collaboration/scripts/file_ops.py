"""Small filesystem helpers. Never overwrite existing files or follow symlinked parents."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


def checked_root(value: str) -> Path:
    root = Path(os.path.abspath(os.path.expanduser(value)))
    for p in (root, *root.parents):
        if p.is_symlink():
            raise ValueError(f"Symlinked root/ancestor is not supported: {p}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"Root is not a directory: {root}")
    return root


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Expected a relative path inside root: {relative!r}")
    target = root / rel
    for p in (target, *target.parents):
        if p == root.parent:
            break
        if p.is_symlink():
            raise ValueError(f"Symlink is not allowed: {p}")
        if p != target and p.exists() and not p.is_dir():
            raise ValueError(f"Parent is not a directory: {p}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes root")
    return target


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plan_files(root: Path, files: dict[str, bytes]) -> list[dict]:
    plan = []
    for rel, data in sorted(files.items()):
        path = safe_path(root, rel)
        if path.exists():
            action = "same" if path.is_file() and path.read_bytes() == data else "conflict"
        else:
            action = "create"
        plan.append({"path": rel, "action": action, "sha256": digest(data)})
    return plan


def create_planned(root: Path, files: dict[str, bytes], plan: list[dict]) -> list[str]:
    if any(item["action"] == "conflict" for item in plan):
        raise ValueError("Existing files differ; no files written. Merge intentionally first.")
    created = []
    for item in plan:
        if item["action"] != "create":
            continue
        path = safe_path(root, item["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        # Recheck after mkdir; exclusive creation prevents overwriting a concurrently created file.
        path = safe_path(root, item["path"])
        with path.open("xb") as stream:
            stream.write(files[item["path"]])
        created.append(item["path"])
    return created
