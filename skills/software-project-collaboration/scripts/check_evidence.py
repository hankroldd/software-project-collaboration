#!/usr/bin/env python3
"""Validate an evidence manifest. Structural validity is NOT proof of product correctness."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from file_ops import checked_root, safe_path

SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "SKIP"}
LAYERS = {"static", "unit", "component", "contract", "integration", "real-integration",
          "browser-mocked", "browser-real", "model-real", "deploy-smoke", "restore", "manual"}


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value) -> bool:
    return isinstance(value, list) and all(nonempty(x) for x in value) and len(set(value)) == len(value)


def file_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def validate(data: object, root: Path, expected_head: str | None = None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"structurally_valid": False, "errors": ["Manifest must be an object"], "warnings": []}
    if data.get("schema_version") != 1 or isinstance(data.get("schema_version"), bool):
        errors.append("schema_version must be 1")
    if not nonempty(data.get("change_id")):
        errors.append("change_id must be nonempty")
    if not isinstance(data.get("risk"), str) or data.get("risk") not in {"R0", "R1", "R2", "R3"}:
        errors.append("risk must be R0/R1/R2/R3")
    for field in ("base_sha", "head_sha"):
        if not isinstance(data.get(field), str) or not SHA.fullmatch(data[field]):
            errors.append(f"{field} must be a full lowercase commit SHA")
    if expected_head and data.get("head_sha") != expected_head:
        errors.append("head_sha differs from expected candidate")
    source_state = data.get("source_state")
    if not isinstance(source_state, str) or source_state not in {"clean", "dirty"}:
        errors.append("source_state must be clean or dirty")
    if source_state == "dirty":
        if not isinstance(data.get("diff_sha256"), str) or not HASH.fullmatch(data["diff_sha256"]):
            errors.append("dirty source requires diff_sha256")
        warnings.append("Dirty-tree evidence must be re-associated with the final submitted candidate")
    env = data.get("environment")
    if not isinstance(env, dict) or not nonempty(env.get("name")) or not nonempty(env.get("identity")):
        errors.append("environment needs a name and actual identity/version")
    required_ac, required_checks = data.get("required_ac"), data.get("required_checks")
    if not string_list(required_ac):
        errors.append("required_ac must contain unique nonempty strings")
        required_ac = []
    if not string_list(required_checks) or not required_checks:
        errors.append("required_checks must contain unique nonempty check IDs")
        required_checks = []
    if isinstance(data.get("risk"), str) and data.get("risk") in {"R2", "R3"} and not required_ac:
        errors.append("R2/R3 needs at least one required acceptance criterion")
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a nonempty list")
        checks = []
    verdict = data.get("verdict")
    if not isinstance(verdict, str) or verdict not in {"PASS", "FAIL", "BLOCKED", "INCOMPLETE"}:
        errors.append("verdict must be PASS/FAIL/BLOCKED/INCOMPLETE")
    if not string_list(data.get("limitations")):
        errors.append("limitations must be a list of distinct strings (empty is allowed)")
    by_id = {}
    passing_ac: set[str] = set()
    for index, check in enumerate(checks):
        label = f"checks[{index}]"
        if not isinstance(check, dict):
            errors.append(f"{label} must be an object")
            continue
        cid = check.get("id")
        if not nonempty(cid):
            errors.append(f"{label} requires an id")
        elif cid in by_id:
            errors.append(f"Duplicate check id: {cid}")
        else:
            by_id[cid] = check
        status = check.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            errors.append(f"{label}: invalid status")
        if not isinstance(check.get("layer"), str) or check.get("layer") not in LAYERS:
            errors.append(f"{label}: layer must distinguish mocked/real evidence")
        if not string_list(check.get("ac")):
            errors.append(f"{label}: ac must be a list of unique IDs")
        if not nonempty(check.get("summary")):
            errors.append(f"{label}: actual observation or reason is required")
        if isinstance(status, str) and status in {"PASS", "FAIL"} and check.get("head_sha") != data.get("head_sha"):
            errors.append(f"{label}: check belongs to a different HEAD")
        command = check.get("command")
        if command is not None and (not isinstance(command, list) or not command or
                                    not all(nonempty(x) for x in command)):
            errors.append(f"{label}: command must be an argv array or null")
        if status == "PASS" and command is not None and (type(check.get("exit_code")) is not int or check["exit_code"] != 0):
            errors.append(f"{label}: passing command requires exit_code 0")
        if status == "SKIP" and not nonempty(check.get("skip_reason")):
            errors.append(f"{label}: skipped checks need a reason")
        counts = {}
        for field in ("collected", "executed", "skipped"):
            value = check.get(field)
            if value is not None:
                if type(value) is not int or value < 0:
                    errors.append(f"{label}: {field} must be a nonnegative integer or null")
                else:
                    counts[field] = value
        if status == "PASS" and counts.get("executed") == 0:
            errors.append(f"{label}: zero executed tests cannot be PASS")
        if counts.get("skipped", 0) and not nonempty(check.get("skip_reason")):
            errors.append(f"{label}: skipped tests need a reason")
        if "collected" in counts and "executed" in counts and counts["executed"] > counts["collected"]:
            warnings.append(f"{label}: executed exceeds collected; explain parametrization/counting unit")
        artifacts = check.get("artifacts")
        if not isinstance(artifacts, list):
            errors.append(f"{label}: artifacts must be a list")
            artifacts = []
        if status == "PASS" and not artifacts:
            errors.append(f"{label}: PASS requires an evidence artifact, not just an assertion")
        for ai, artifact in enumerate(artifacts):
            alabel = f"{label}.artifacts[{ai}]"
            if not isinstance(artifact, dict):
                errors.append(f"{alabel}: artifact must be an object")
                continue
            has_path, has_url = nonempty(artifact.get("path")), nonempty(artifact.get("url"))
            if has_path == has_url:
                errors.append(f"{alabel}: specify exactly one path or immutable URL")
                continue
            sha = artifact.get("sha256")
            if not isinstance(sha, str) or not HASH.fullmatch(sha):
                errors.append(f"{alabel}: valid sha256 required")
                continue
            if has_url:
                u = urlsplit(artifact["url"])
                if u.scheme not in {"http", "https"} or not u.netloc or u.username or u.password:
                    errors.append(f"{alabel}: invalid evidence URL")
                else:
                    warnings.append(f"{alabel}: external artifact not fetched; immutability/hash not verified")
                continue
            try:
                p = safe_path(root, artifact["path"])
                if not p.is_file():
                    errors.append(f"{alabel}: local evidence file does not exist")
                elif file_hash(p) != sha:
                    errors.append(f"{alabel}: evidence hash mismatch")
            except (OSError, ValueError) as exc:
                errors.append(f"{alabel}: {exc}")
        if status == "PASS" and string_list(check.get("ac")):
            passing_ac.update(check["ac"])
    for cid in required_checks:
        if cid not in by_id:
            errors.append(f"Missing required check: {cid}")
    if verdict == "PASS":
        for cid in required_checks:
            if cid in by_id and by_id[cid].get("status") != "PASS":
                errors.append(f"Required check is not PASS: {cid}")
        for cid, check in by_id.items():
            if check.get("status") == "FAIL":
                errors.append(f"Unresolved FAIL cannot be hidden by overall PASS: {cid}")
        for ac in required_ac:
            if ac not in passing_ac:
                errors.append(f"Required acceptance criterion lacks passing evidence: {ac}")
        if source_state != "clean":
            errors.append("Overall PASS requires a clean, identifiable submitted candidate")
    elif not data.get("limitations"):
        errors.append("Non-PASS verdict requires limitations/remaining work")
    return {"structurally_valid": not errors, "declared_verdict": verdict,
            "errors": errors, "warnings": warnings,
            "meaning": "Only structure, identity, local hashes and internal consistency were checked; no product acceptance was performed."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Evidence root directory")
    parser.add_argument("--file", required=True, help="Manifest path relative to evidence root")
    parser.add_argument("--expected-head", help="Exact expected full lowercase SHA")
    parser.add_argument("--require-pass", action="store_true", help="Exit 3 for a structurally valid non-PASS report")
    args = parser.parse_args()
    try:
        root = checked_root(args.root)
        path = safe_path(root, args.file)
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Manifest exceeds 2 MiB; reference large artifacts instead")
        if args.expected_head and not SHA.fullmatch(args.expected_head):
            raise ValueError("--expected-head needs a full lowercase SHA")
        data = json.loads(path.read_text(encoding="utf-8"))
        result = validate(data, root, args.expected_head)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["structurally_valid"]:
            return 2
        return 3 if args.require_pass and result.get("declared_verdict") != "PASS" else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"structurally_valid": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
