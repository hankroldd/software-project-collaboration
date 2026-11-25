#!/usr/bin/env python3
"""Read-only Git identity, current-branch history and diff index; this is not a code review."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

READ_ONLY_GIT = ["git", "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
                 "-c", "log.showSignature=false"]

def git(repo: Path, *args: str, allow_failure: bool = False) -> bytes:
    run = subprocess.run([*READ_ONLY_GIT, "-C", str(repo), *args],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    if run.returncode and not allow_failure:
        # Do not dump remote URLs, config values or arbitrary stderr.
        raise ValueError(f"Git read failed: {args[0]} (exit {run.returncode})")
    return run.stdout


def decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--days", type=int, default=7, help="Current-branch history window; 1–365")
    parser.add_argument("--base", help="Known commit SHA; never defaults to HEAD~1")
    parser.add_argument("--limit", type=int, default=200, help="Maximum recent commits; 1–1000")
    args = parser.parse_args()
    try:
        if not 1 <= args.days <= 365 or not 1 <= args.limit <= 1000:
            raise ValueError("Invalid days or limit")
        if args.base and not re.fullmatch(r"[0-9a-fA-F]{7,64}", args.base):
            raise ValueError("--base must be a known commit SHA")
        repo = Path(args.repo).expanduser().resolve(strict=True)
        root = Path(decode(git(repo, "rev-parse", "--show-toplevel")))
        head = decode(git(root, "rev-parse", "HEAD"))
        branch = decode(git(root, "branch", "--show-current")) or "DETACHED"
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).isoformat()
        raw = git(root, "log", f"--since={since}", f"--max-count={args.limit + 1}",
                  "--format=%H%x1f%cI%x1f%s")
        commits = []
        for line in decode(raw).splitlines():
            fields = line.split("\x1f", 2)
            if len(fields) == 3:
                commits.append(dict(zip(("sha", "committed_at", "subject"), fields)))
        # Leading spaces encode the index/worktree columns; preserve them exactly.
        status = git(root, "status", "--short", "--untracked-files=normal").decode(
            "utf-8", errors="replace").rstrip("\r\n")
        diff = git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--")
        result = {"repository": str(root), "branch": branch, "head_sha": head,
                  "source_state": "dirty" if status else "clean", "status": status.splitlines(),
                  "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
                  "recent_scope": "current branch only; commit timestamps, not all work",
                  "since_utc": since, "recent_commits": commits[:args.limit],
                  "truncated": len(commits) > args.limit,
                  "limitations": ["No code or tests were reviewed or executed.",
                                  "Untracked content is not included in tracked_diff_sha256.",
                                  "No fetch: remote state may be newer."]}
        if args.base:
            base = decode(git(root, "rev-parse", f"{args.base}^{{commit}}"))
            ancestral = subprocess.run([*READ_ONLY_GIT, "-C", str(root), "merge-base",
                                        "--is-ancestor", base, head], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=30).returncode
            if ancestral:
                raise ValueError("BASE is not an ancestor of HEAD; choose the real task base")
            result["base_sha"] = base
            result["range_empty"] = base == head
            result["changed_files"] = decode(git(root, "diff", "--no-ext-diff", "--no-textconv",
                                                   "--name-status", base, head, "--")).splitlines()
            result["diff_stat"] = decode(git(root, "diff", "--no-ext-diff", "--no-textconv",
                                               "--stat", base, head, "--"))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
