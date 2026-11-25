#!/usr/bin/env python3
"""Observe project-local skill copies and links; never install, repair or select a host."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import errno
import hashlib
import itertools
import json
import os
import re
import stat
from pathlib import Path

LOCATIONS = (".agents/skills", ".claude/skills", ".opencode/skills")
DEFAULT_SKILL = "software-project-collaboration"


class JsonParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


class StopScan(Exception):
    pass


class ChangedDuringRead(Exception):
    pass


def signature(info: os.stat_result) -> tuple:
    # Access times can change during a read and are deliberately excluded.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def unsupported_reparse(info: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(info, "st_file_attributes", 0) & flag) and not stat.S_ISLNK(info.st_mode)


def version_metadata(data: bytes) -> dict:
    """Read only a direct metadata.version scalar; this is not a YAML validator."""
    unknown = {"version": None, "version_status": "unknown"}
    try:
        lines = data.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return unknown
    if not lines or lines[0].strip() != "---":
        return unknown
    end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if end is None:
        return unknown
    front = lines[1:end]
    headers = [(i, re.fullmatch(r"metadata\s*:\s*(.*)", line))
               for i, line in enumerate(front) if re.match(r"^metadata\s*:", line)]
    if len(headers) != 1:
        return unknown
    index, header = headers[0]
    if not header or (header[1] and not header[1].startswith("#")):
        return unknown  # Inline maps, aliases and tags need a real YAML parser.
    children = []
    for line in front[index + 1:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            break
        indent = len(line) - len(line.lstrip(" "))
        if "\t" in line[:indent + 1]:
            return unknown
        children.append((indent, line[indent:]))
    if not children:
        return unknown
    direct_indent = min(indent for indent, _ in children)
    values = [match[1] for indent, line in children
              if indent == direct_indent
              and (match := re.fullmatch(r"version\s*:\s*(.*)", line))]
    if len(values) != 1:
        return unknown
    raw = values[0].strip()
    try:
        if raw.startswith('"'):
            value, stop = json.JSONDecoder().raw_decode(raw)
            tail = raw[stop:].strip()
            if tail and not tail.startswith("#"):
                return unknown
        elif raw.startswith("'"):
            match = re.fullmatch(r"'((?:[^']|'')*)'(?:\s+#.*)?", raw)
            if not match:
                return unknown
            value = match[1].replace("''", "'")
        else:
            match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.+\-]*)(?:\s+#.*)?", raw)
            if not match or match[1].lower() in ("null", "true", "false"):
                return unknown
            value = match[1]
        if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value):
            return unknown
        return {"version": value, "version_status": "observed"}
    except (ValueError, TypeError):
        return unknown


def read_regular(path: Path, before: os.stat_result, capture: bool) -> tuple:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    checksum = hashlib.sha256()
    parts = []
    count = 0
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or signature(opened) != signature(before):
            raise ChangedDuringRead("File changed before opening")
        while count < before.st_size:
            chunk = stream.read(min(65536, before.st_size - count))
            if not chunk:
                break
            count += len(chunk)
            checksum.update(chunk)
            if capture:
                parts.append(chunk)
        if (count != before.st_size
                or signature(os.fstat(stream.fileno())) != signature(before)
                or signature(path.lstat()) != signature(before)):
            raise ChangedDuringRead("File changed while reading")
    return checksum.digest(), count, b"".join(parts) if capture else None


def scan_tree(target: Path, limits: dict) -> dict:
    result = {"metadata": {"version": None, "version_status": "unknown"},
              "fingerprint": None, "files_seen": 0, "files_hashed": 0, "bytes_hashed": 0,
              "entries_seen": 0, "excluded_entries": 0, "issues": []}
    records = []
    skill_read = False
    reserved_bytes = 0

    def issue(code: str, relative: str, detail: str) -> None:
        result["issues"].append({"code": code, "path": relative, "detail": detail})

    def walk(directory: Path, depth: int) -> None:
        nonlocal skill_read, reserved_bytes
        relative_dir = directory.relative_to(target).as_posix()
        observed_path = relative_dir
        if depth > limits["max_depth"]:
            issue("limit_exceeded", relative_dir, "Directory depth limit reached")
            raise StopScan
        try:
            before = directory.lstat()
            if unsupported_reparse(before):
                issue("unsafe", relative_dir, "Non-symlink reparse point was not traversed")
                return
            if not stat.S_ISDIR(before.st_mode):
                raise ChangedDuringRead("Directory changed before enumeration")
            with os.scandir(directory) as entries:
                for entry in entries:
                    result["entries_seen"] += 1
                    relative = (directory / entry.name).relative_to(target).as_posix()
                    observed_path = relative
                    if result["entries_seen"] > limits["max_entries"]:
                        issue("limit_exceeded", relative, "Entry count limit reached")
                        raise StopScan
                    path = directory / entry.name
                    info = path.lstat()
                    if unsupported_reparse(info):
                        issue("unsafe", relative, "Non-symlink reparse point was not read or traversed")
                    elif stat.S_ISLNK(info.st_mode):
                        issue("unsafe", relative, "Internal symlink was not followed; fingerprint unknown")
                    elif entry.name == "__pycache__" or (stat.S_ISREG(info.st_mode)
                                                        and entry.name.endswith(".pyc")):
                        result["excluded_entries"] += 1
                    elif stat.S_ISDIR(info.st_mode):
                        walk(path, depth + 1)
                    elif stat.S_ISREG(info.st_mode):
                        result["files_seen"] += 1
                        if (result["files_seen"] > limits["max_files"]
                                or info.st_size > limits["max_file_bytes"]
                                or reserved_bytes + info.st_size > limits["max_total_bytes"]):
                            issue("limit_exceeded", relative, "File count or byte limit reached")
                            raise StopScan
                        reserved_bytes += info.st_size
                        digest, size, data = read_regular(path, info, relative == "SKILL.md")
                        records.append((relative, size, digest))
                        result["files_hashed"] += 1
                        result["bytes_hashed"] += size
                        if relative == "SKILL.md":
                            result["metadata"] = version_metadata(data)
                            skill_read = True
                    else:
                        issue("unsafe", relative, "Non-regular entry was not read; fingerprint unknown")
            observed_path = relative_dir
            if signature(directory.lstat()) != signature(before):
                raise ChangedDuringRead("Directory changed while enumerating")
        except ChangedDuringRead as exc:
            issue("changed", observed_path, str(exc))
        except FileNotFoundError:
            issue("changed", observed_path, "Entry disappeared during observation")
        except OSError as exc:
            issue("read_error", observed_path, str(exc))

    try:
        walk(target, 0)
    except StopScan:
        pass
    if not result["issues"] and not skill_read:
        issue("invalid_skill", "SKILL.md", "Required regular SKILL.md is missing")
    if not result["issues"]:
        digest = hashlib.sha256(b"skill-file-content-v1\0")
        for relative, size, file_hash in sorted(records):
            name = relative.encode("utf-8", errors="surrogateescape")
            digest.update(len(name).to_bytes(8, "big"))
            digest.update(name)
            digest.update(size.to_bytes(8, "big"))
            digest.update(file_hash)
        result["fingerprint"] = digest.hexdigest()
    result["state"] = next((code for code in ("read_error", "unsafe", "changed", "limit_exceeded",
                                              "invalid_skill")
                            if any(item["code"] == code for item in result["issues"])), "ok")
    return result


def inspect_location(root: Path, location: str, skill: str, limits: dict) -> dict:
    candidate = root / location / skill
    result = {"location": location, "path": str(candidate), "kind": "unknown", "state": "unknown",
              "resolved_target": None, "external": None, "link_target": None,
              "metadata": {"version": None, "version_status": "unknown"},
              "fingerprint": None, "issues": []}

    def stop(state: str, detail: str, path: Path = candidate) -> dict:
        result["state"] = state
        result["issues"].append({"code": state, "path": str(path), "detail": detail})
        return result

    try:
        parent = root
        for part in Path(location).parts:
            parent /= part
            info = parent.lstat()
            if unsupported_reparse(info):
                return stop("unsafe", "Search parent is a non-symlink reparse point; not traversed", parent)
            if stat.S_ISLNK(info.st_mode):
                return stop("unsafe", "Search parent is a symlink; only the final skill link is followed", parent)
            if not stat.S_ISDIR(info.st_mode):
                return stop("not_directory", "Search parent is not a directory", parent)
        before = candidate.lstat()
        if unsupported_reparse(before):
            result["kind"] = "reparse_point"
            return stop("unsafe", "Final entry is a non-symlink reparse point; not resolved or traversed")
        is_link = stat.S_ISLNK(before.st_mode)
        result["kind"] = "symlink" if is_link else "directory" if stat.S_ISDIR(before.st_mode) else "other"
        if is_link:
            result["link_target"] = os.readlink(candidate)
            try:
                target = candidate.resolve(strict=True)
            except (FileNotFoundError, NotADirectoryError, RuntimeError):
                return stop("broken_link", "Link target is missing or cannot be resolved")
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    return stop("broken_link", "Link cycle cannot be resolved")
                raise
        else:
            target = candidate
        result["resolved_target"] = str(target)
        result["external"] = not target.is_relative_to(root)
        if not target.is_dir():
            return stop("not_directory", "Resolved skill target is not a directory")
        result.update(scan_tree(target, limits))
        if signature(candidate.lstat()) != signature(before):
            result["fingerprint"] = None
            result["state"] = "changed"
            result["issues"].append({"code": "changed", "path": str(candidate),
                                     "detail": "Installation entry changed during observation"})
        return result
    except FileNotFoundError:
        if result["kind"] == "unknown":
            result["kind"] = "missing"
            return stop("missing", "Installation path is absent")
        result["fingerprint"] = None
        return stop("changed", "Installation entry disappeared during observation")
    except OSError as exc:
        result["fingerprint"] = None
        return stop("read_error", str(exc))


def inspect_project(root: Path, skill: str, limits: dict) -> dict:
    installations = [inspect_location(root, location, skill, limits) for location in LOCATIONS]
    comparisons = []
    for left, right in itertools.combinations(installations, 2):
        targets = (left["resolved_target"], right["resolved_target"])
        fingerprints = (left["fingerprint"], right["fingerprint"])
        comparisons.append({"left": left["location"], "right": right["location"],
                            "target": ("same" if targets[0] == targets[1] else "different")
                            if all(targets) else "unknown",
                            "content": ("same" if fingerprints[0] == fingerprints[1] else "drift")
                            if all(fingerprints) else "unknown"})
    return {"schema_version": 1, "root": str(root), "skill": skill,
            "observations_only": {"host_loading": "not_checked", "global_priority": "not_checked",
                                  "home_search": False, "atomic_snapshot": False},
            "fingerprint_format": "sha256: skill-file-content-v1; sorted relative names, sizes and file hashes",
            "fingerprint_excludes": ["__pycache__", "regular *.pyc files", "empty directories",
                                     "permissions", "timestamps"],
            "limits": limits, "installations": installations, "comparisons": comparisons,
            "summary": {"observed_directories_or_links": sum(item["kind"] in ("directory", "symlink")
                                                             for item in installations),
                        "missing": [item["location"] for item in installations if item["state"] == "missing"],
                        "has_observed_drift": any(pair["content"] == "drift" for pair in comparisons),
                        "unknown_fingerprints": [item["location"] for item in installations
                                                 if item["fingerprint"] is None],
                        "has_read_errors": any(issue["code"] == "read_error" for item in installations
                                               for issue in item["issues"])}}


def main(argv: list[str] | None = None) -> int:
    parser = JsonParser(description=__doc__, epilog=(
        "Exit codes: 0 = observations produced, including missing/drift/broken links/unsafe or limited trees; "
        "2 = invalid input or a read error. JSON output except --help. "
        "Only explicit --root paths are checked; no HOME/global search. Final skill-directory links may "
        "resolve outside the project (external=true); search-parent and internal links are not followed. "
        "Detected non-symlink reparse points are reported unsafe without traversal. "
        "metadata.version supports only a simple direct frontmatter scalar; otherwise unknown. "
        "This is not an atomic snapshot: concurrent directory changes can invalidate observations. "
        "No claim about actual host loading or global precedence; no files are written."))
    parser.add_argument("--root", required=True, help="Existing project directory; no default or HOME expansion")
    parser.add_argument("--skill", default=DEFAULT_SKILL, help="Exact skill directory name")
    parser.add_argument("--max-files", type=int, default=1000, help="Maximum regular files per installation (default: 1000)")
    parser.add_argument("--max-file-bytes", type=int, default=2 * 1024 * 1024, help="Maximum bytes per file (default: 2097152)")
    parser.add_argument("--max-total-bytes", type=int, default=32 * 1024 * 1024, help="Maximum bytes per installation (default: 33554432)")
    try:
        args = parser.parse_args(argv)
        if not args.root.strip():
            raise ValueError("--root must not be empty")
        if len(args.skill) > 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.skill):
            raise ValueError("--skill must be a lowercase skill name of at most 64 characters")
        if min(args.max_files, args.max_file_bytes, args.max_total_bytes) < 1:
            raise ValueError("All limits must be positive integers")
        root = Path(args.root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("--root must be an existing directory")
        limits = {"max_files": args.max_files, "max_file_bytes": args.max_file_bytes,
                  "max_total_bytes": args.max_total_bytes, "max_entries": args.max_files * 4,
                  "max_depth": 64}
        result = inspect_project(root, args.skill, limits)
        print(json.dumps(result, indent=2))
        return 2 if result["summary"]["has_read_errors"] else 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
