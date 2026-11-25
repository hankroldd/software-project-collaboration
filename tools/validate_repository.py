#!/usr/bin/env python3
"""Validate this maintained package shape and optional content manifest; standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

NAME = "software-project-collaboration"
ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / NAME
MANIFEST = ROOT / "release-manifest.json"
SKIP_PARTS = {".git", "__pycache__", ".venv"}
PRIVATE_MARKERS = (
    r"libfile_[a-z0-9]{20,}", r"skill-[a-f0-9]{32}",
    r"/workspace/" + r"scratch/", r"/root/\.codex/",
    r"chatgpt\.com/(?:skills\?skill_id|library\?file_id)=",
    r"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}",
)


def collect(root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"Public candidate contains symlink: {relative}")
        if path.is_file() and relative.as_posix() != "release-manifest.json":
            result[relative.as_posix()] = path.read_bytes()
    return result


def structural_checks(files: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    required = ["README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md",
                "docs/RELEASING.md", ".github/workflows/validate.yml", "tools/validate_repository.py",
                f"skills/{NAME}/SKILL.md", f"skills/{NAME}/LICENSE.txt"]
    for relative in required:
        if relative not in files:
            errors.append(f"Missing file: {relative}")
    skill_text = files.get(f"skills/{NAME}/SKILL.md", b"").decode("utf-8")
    if not skill_text.startswith("---\n") or "\n---\n" not in skill_text[4:]:
        errors.append("SKILL.md needs YAML frontmatter delimiters")
    frontmatter = skill_text.split("---", 2)[1] if skill_text.startswith("---") else ""
    if not re.search(rf"^name: {NAME}$", frontmatter, re.M):
        errors.append("Skill name must match its directory")
    if not re.search(r"^description: .+", frontmatter, re.M):
        errors.append("Missing nonempty description")
    if not re.search(r'^  version: "[0-9]+\.[0-9]+\.[0-9]+"$', frontmatter, re.M):
        errors.append("Expected maintained metadata.version")
    if len(skill_text.splitlines()) >= 500:
        errors.append("Entry exceeds this project's 500-line maintenance budget")
    if files.get("LICENSE") != files.get(f"skills/{NAME}/LICENSE.txt"):
        errors.append("Root and installed skill licenses differ")
    ui = files.get(f"skills/{NAME}/agents/openai.yaml", b"").decode("utf-8")
    if re.search(r"^(policy|dependencies):", ui, re.M):
        errors.append("Public UI metadata must not carry managed policy/dependencies")
    for relative, data in files.items():
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in PRIVATE_MARKERS:
            if re.search(pattern, text):
                errors.append(f"Potential private identifier/credential in {relative}; inspect without printing matched value")
                break
        # Templates have links for their future location; do not resolve them here.
        if not (relative == "README.md" or relative == f"skills/{NAME}/SKILL.md"
                or relative.startswith(f"skills/{NAME}/references/")) or not relative.endswith(".md"):
            continue
        for link in re.findall(r"(?<!!)\[[^\]]+\]\(([^\s)]+)\)", text):
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = ((ROOT / relative).parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(ROOT) or not target.exists():
                errors.append(f"Missing/escaping local link in {relative}: {link}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check-manifest", action="store_true", help="Fail if file set or SHA256 differs from release-manifest.json")
    group.add_argument("--refresh-manifest", action="store_true", help="Explicitly rewrite hashes after reviewed edits; not a test or release attestation")
    args = parser.parse_args()
    try:
        files = collect(ROOT)
        errors = structural_checks(files)
        hashes = {relative: hashlib.sha256(data).hexdigest() for relative, data in sorted(files.items())}
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if (args.check_manifest or args.refresh_manifest) else None
        if (args.check_manifest or args.refresh_manifest) and (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
                                     or manifest.get("skill_name") != NAME or not isinstance(manifest.get("files"), dict)):
            errors.append("Unsupported manifest structure")
        version_match = re.search(r'^  version: "([0-9]+\.[0-9]+\.[0-9]+)"$', files.get(f"skills/{NAME}/SKILL.md", b"").decode(), re.M)
        if args.check_manifest and not errors and manifest.get("version") != version_match.group(1):
            errors.append("Manifest version differs from skill metadata")
        if args.check_manifest and not errors and manifest["files"] != hashes:
            errors.append("Manifest differs from current file set/content; review changes before explicitly refreshing")
        refreshed = False
        if args.refresh_manifest and not errors:
            match = re.search(r'^  version: "([0-9]+\.[0-9]+\.[0-9]+)"$', files[f"skills/{NAME}/SKILL.md"].decode(), re.M)
            if not match:
                errors.append("Expected maintained metadata.version")
            else:
                manifest["version"] = match.group(1)
                manifest["files"] = hashes
                MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                refreshed = True
        print(json.dumps({"valid": not errors, "files": len(files), "errors": errors,
                          "manifest_checked": bool(args.check_manifest and not errors), "manifest_refreshed": refreshed,
                          "scope": "Maintained package conventions, local links and marker checks; not a full YAML/security/runtime audit."},
                         ensure_ascii=False, indent=2))
        return 1 if errors else 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
