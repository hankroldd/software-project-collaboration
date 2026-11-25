#!/usr/bin/env python3
"""Synthetic filesystem checks for the read-only project installation inspector."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import contextlib
import errno
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inspect_installation as inspector

SCRIPT = Path(__file__).with_name("inspect_installation.py")
SKILL = "software-project-collaboration"
FRONT = b'---\nname: software-project-collaboration\nmetadata:\n  version: "0.2.0"\n---\n# Synthetic\n'


def snapshot(root: Path) -> dict:
    """Record names, contents and write-related metadata, without following links."""
    result = {}
    pending = [root]
    while pending:
        path = pending.pop()
        info = path.lstat()
        relative = path.relative_to(root).as_posix()
        data = (stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns,
                info.st_ctime_ns, info.st_mode)
        if path.is_symlink():
            data += (os.readlink(path),)
        elif stat.S_ISREG(info.st_mode):
            data += (hashlib.sha256(path.read_bytes()).hexdigest(),)
        elif stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
        result[relative] = data
    return result


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-installation-check-")
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def source(self, path: Path) -> Path:
        path.mkdir(parents=True)
        (path / "SKILL.md").write_bytes(FRONT)
        (path / "notes.txt").write_bytes(b"synthetic same contents\n")
        return path

    def install(self, location: str = ".agents/skills", skill: str = SKILL) -> Path:
        return self.source(self.root / location / skill)

    def link(self, location: str, target: Path, relative: bool = False) -> Path:
        link = self.root / location / SKILL
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            link.symlink_to(os.path.relpath(target, link.parent) if relative else target,
                            target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"This test environment cannot create symlinks: {exc}")
        return link

    def cli(self, *args: str, env: dict | None = None, code: int = 0) -> dict:
        run = subprocess.run([sys.executable, "-B", str(SCRIPT), *args],
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=15, env=env)
        self.assertEqual(run.returncode, code, run.stdout + run.stderr)
        self.assertEqual(run.stderr, "", run.stderr)
        return json.loads(run.stdout)

    def inspect(self, *args: str, **kwargs) -> dict:
        return self.cli("--root", str(self.root), *args, **kwargs)

    def at(self, report: dict, location: str = ".agents/skills") -> dict:
        return next(item for item in report["installations"] if item["location"] == location)

    def test_missing_paths_are_observations_and_do_not_create_directories(self):
        before = snapshot(self.base)
        report = self.inspect()
        self.assertEqual([item["state"] for item in report["installations"]], ["missing"] * 3)
        self.assertEqual(snapshot(self.base), before)

    def test_copy_has_version_resolved_target_and_stable_fingerprint(self):
        path = self.install()
        first = self.at(self.inspect())
        second = self.at(self.inspect())
        self.assertEqual(first["state"], "ok")
        self.assertEqual(first["resolved_target"], str(path))
        self.assertFalse(first["external"])
        self.assertEqual(first["metadata"]["version"], "0.2.0")
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_three_equal_copies_report_equal_content_and_distinct_targets(self):
        source = self.install()
        for location in inspector.LOCATIONS[1:]:
            shutil.copytree(source, self.root / location / SKILL)
        report = self.inspect()
        self.assertEqual(report["summary"]["observed_directories_or_links"], 3)
        self.assertTrue(all(pair["content"] == "same" for pair in report["comparisons"]))
        self.assertTrue(all(pair["target"] == "different" for pair in report["comparisons"]))

    def test_external_final_links_report_same_target_and_content(self):
        source = self.source(self.base / "canonical")
        self.link(".agents/skills", source, relative=True)
        self.link(".claude/skills", source)
        report = self.inspect()
        pair = report["comparisons"][0]
        self.assertEqual((pair["target"], pair["content"]), ("same", "same"))
        for location in inspector.LOCATIONS[:2]:
            item = self.at(report, location)
            self.assertEqual(item["resolved_target"], str(source))
            self.assertTrue(item["external"])
            self.assertEqual(item["kind"], "symlink")

    def test_final_link_inside_explicit_root_is_not_external(self):
        source = self.source(self.root / "canonical")
        self.link(".opencode/skills", source, relative=True)
        item = self.at(self.inspect(), ".opencode/skills")
        self.assertEqual(item["state"], "ok")
        self.assertFalse(item["external"])

    def test_same_version_does_not_hide_content_drift(self):
        self.install()
        changed = self.install(".claude/skills")
        (changed / "notes.txt").write_text("changed contents", encoding="utf-8")
        report = self.inspect()
        self.assertTrue(report["summary"]["has_observed_drift"])
        self.assertEqual(report["comparisons"][0]["content"], "drift")
        self.assertEqual(self.at(report)["metadata"], self.at(report, ".claude/skills")["metadata"])

    def test_renamed_file_changes_fingerprint_even_when_bytes_match(self):
        first = self.install()
        second = self.install(".claude/skills")
        (second / "notes.txt").rename(second / "renamed.txt")
        report = self.inspect()
        self.assertNotEqual(self.at(report)["fingerprint"], self.at(report, ".claude/skills")["fingerprint"])
        self.assertTrue((first / "notes.txt").is_file())

    def test_dangling_final_link_is_reported_without_read_error(self):
        self.link(".agents/skills", self.base / "absent")
        report = self.inspect()
        item = self.at(report)
        self.assertEqual(item["state"], "broken_link")
        self.assertIsNone(item["resolved_target"])
        self.assertIsNone(item["fingerprint"])
        self.assertFalse(report["summary"]["has_read_errors"])

    def test_final_link_cycle_is_a_broken_link(self):
        target = self.root / ".agents/skills" / SKILL
        self.link(".agents/skills", target)
        self.assertEqual(self.at(self.inspect())["state"], "broken_link")

    def test_internal_file_link_is_not_read_or_hashed(self):
        path = self.install()
        outside = self.base / "outside.txt"
        outside.write_bytes(b"must not read external contents" * 100)
        try:
            (path / "linked.txt").symlink_to(outside)
        except OSError as exc:
            self.skipTest(str(exc))
        item = self.at(self.inspect())
        self.assertEqual(item["state"], "unsafe")
        self.assertIsNone(item["fingerprint"])
        self.assertEqual(item["files_hashed"], 2)
        self.assertEqual(item["bytes_hashed"], len(FRONT) + len(b"synthetic same contents\n"))

    def test_internal_directory_link_is_not_traversed(self):
        path = self.install()
        outside = self.source(self.base / "outside")
        try:
            (path / "external-tree").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(str(exc))
        item = self.at(self.inspect())
        self.assertEqual(item["state"], "unsafe")
        self.assertEqual(item["files_hashed"], 2)
        self.assertIsNone(item["fingerprint"])

    def test_search_parent_link_is_reported_without_following(self):
        outside = self.base / "outside-skills"
        self.source(outside / SKILL)
        parent = self.root / ".claude"
        parent.mkdir()
        try:
            (parent / "skills").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(str(exc))
        item = self.at(self.inspect(), ".claude/skills")
        self.assertEqual(item["state"], "unsafe")
        self.assertIsNone(item["resolved_target"])
        self.assertIsNone(item["fingerprint"])

    def test_regular_file_at_installation_path_is_not_a_skill_directory(self):
        path = self.root / ".agents/skills" / SKILL
        path.parent.mkdir(parents=True)
        path.write_text("not a directory", encoding="utf-8")
        self.assertEqual(self.at(self.inspect())["state"], "not_directory")

    def test_simulated_non_symlink_reparse_points_are_not_read_or_traversed(self):
        installed = self.install()
        internal = installed / "nested"
        internal.mkdir()
        original_lstat, original_scandir, original_open = Path.lstat, os.scandir, os.open
        flag = 0x400
        for blocked in (self.root / ".agents", installed.parent, installed,
                        internal, installed / "notes.txt"):
            with self.subTest(blocked=blocked):
                def marked_lstat(path, *args, **kwargs):
                    info = original_lstat(path, *args, **kwargs)
                    if path != blocked:
                        return info
                    values = {name: getattr(info, name) for name in
                              ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")}
                    return SimpleNamespace(**values, st_file_attributes=flag)

                def guarded_scandir(path):
                    self.assertNotEqual(Path(path), blocked, "Reparse directory was traversed")
                    return original_scandir(path)

                def guarded_open(path, *args, **kwargs):
                    self.assertNotEqual(Path(path), blocked, "Reparse file was read")
                    return original_open(path, *args, **kwargs)

                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    stack.enter_context(mock.patch.object(stat, "FILE_ATTRIBUTE_REPARSE_POINT", flag, create=True))
                    stack.enter_context(mock.patch.object(Path, "lstat", marked_lstat))
                    stack.enter_context(mock.patch.object(inspector.os, "scandir", guarded_scandir))
                    stack.enter_context(mock.patch.object(inspector.os, "open", guarded_open))
                    stack.enter_context(contextlib.redirect_stdout(output))
                    code = inspector.main(["--root", str(self.root)])
                item = self.at(json.loads(output.getvalue()))
                self.assertEqual(code, 0)
                self.assertEqual(item["state"], "unsafe")
                self.assertIsNone(item["fingerprint"])

    def test_missing_skill_markdown_does_not_produce_valid_fingerprint(self):
        path = self.install()
        (path / "SKILL.md").unlink()
        item = self.at(self.inspect())
        self.assertEqual(item["state"], "invalid_skill")
        self.assertIsNone(item["fingerprint"])

    def test_limits_make_partial_fingerprint_unknown(self):
        path = self.install()
        size = sum(file.stat().st_size for file in path.iterdir())
        for args in (("--max-files", "1"), ("--max-file-bytes", "1"),
                     ("--max-total-bytes", str(size - 1))):
            with self.subTest(args=args):
                item = self.at(self.inspect(*args))
                self.assertEqual(item["state"], "limit_exceeded")
                self.assertIsNone(item["fingerprint"])

    def test_directory_entries_are_bounded_even_without_files(self):
        path = self.root / ".agents/skills" / SKILL
        path.mkdir(parents=True)
        for number in range(6):
            (path / f"empty-{number}").mkdir()
        item = self.at(self.inspect("--max-files", "1"))
        self.assertEqual(item["state"], "limit_exceeded")
        self.assertLessEqual(item["entries_seen"], 5)

    def test_bytecode_and_cache_directories_do_not_create_false_drift(self):
        first = self.install()
        second = self.install(".claude/skills")
        (first / "__pycache__").mkdir()
        (first / "__pycache__/local.pyc").write_bytes(b"generated")
        (first / "extra.pyc").write_bytes(b"also generated")
        (second / "extra.pyc").write_bytes(b"different generated data")
        self.assertEqual(self.inspect()["comparisons"][0]["content"], "same")

    def test_reads_do_not_change_files_or_search_home(self):
        self.install()
        self.source(self.base / "outside-project/.claude/skills" / SKILL)
        before = snapshot(self.base)
        original_scandir = os.scandir

        def project_scandir(path):
            self.assertTrue(Path(path).is_relative_to(self.root), "Unexpected scan outside explicit root")
            return original_scandir(path)

        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            for owner, name in ((Path, "home"), (Path, "expanduser"), (os.path, "expanduser")):
                stack.enter_context(mock.patch.object(owner, name,
                                    side_effect=AssertionError("Implicit home lookup is forbidden")))
            stack.enter_context(mock.patch.object(inspector.os, "scandir", side_effect=project_scandir))
            stack.enter_context(contextlib.redirect_stdout(output))
            code = inspector.main(["--root", str(self.root)])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(self.at(report, ".claude/skills")["state"], "missing")
        self.assertFalse(report["observations_only"]["home_search"])
        self.assertEqual(snapshot(self.base), before)

    def test_invalid_inputs_are_json_and_exit_two(self):
        regular = self.base / "file"
        regular.write_text("file", encoding="utf-8")
        cases = [(), ("--root", ""), ("--root", str(self.base / "absent")),
                 ("--root", str(regular)), ("--root", str(self.root), "--max-files", "0"),
                 ("--root", str(self.root), "--skill", "../escape")]
        for args in cases:
            with self.subTest(args=args):
                self.assertIn("error", self.cli(*args, code=2))

    def test_read_error_preserves_other_observations_and_returns_two(self):
        self.install()
        output = io.StringIO()
        with mock.patch.object(inspector.os, "open", side_effect=PermissionError(errno.EACCES, "synthetic denial")):
            with contextlib.redirect_stdout(output):
                code = inspector.main(["--root", str(self.root)])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(self.at(report)["state"], "read_error")
        self.assertEqual(self.at(report, ".opencode/skills")["state"], "missing")

    def test_file_change_during_observation_invalidates_fingerprint(self):
        self.install()
        original = inspector.read_regular

        def change_then_read(path, before, capture):
            path.write_bytes(path.read_bytes() + b"concurrent change")
            return original(path, before, capture)

        output = io.StringIO()
        with mock.patch.object(inspector, "read_regular", side_effect=change_then_read):
            with contextlib.redirect_stdout(output):
                code = inspector.main(["--root", str(self.root)])
        item = self.at(json.loads(output.getvalue()))
        self.assertEqual(code, 0)
        self.assertEqual(item["state"], "changed")
        self.assertIsNone(item["fingerprint"])

    def test_restricted_metadata_parser_reports_complex_or_ambiguous_values_unknown(self):
        bodies = [b"metadata: {version: '1.0'}", b"metadata:\n  version: |\n    1.0",
                  b"metadata:\n  version: '1.0'\n  version: '2.0'",
                  b"metadata:\n  nested:\n    version: '9.0'",
                  b"metadata:\n  version: *alias", b"metadata: *alias", b"name: synthetic"]
        for body in bodies:
            with self.subTest(body=body):
                result = inspector.version_metadata(b"---\n" + body + b"\n---\n")
                self.assertEqual(result, {"version": None, "version_status": "unknown"})
        for scalar in (b"0.2.0", b"'0.2.0'", b'"0.2.0" # release'):
            with self.subTest(scalar=scalar):
                result = inspector.version_metadata(b"---\nmetadata:\n  version: " + scalar + b"\n---\n")
                self.assertEqual(result["version"], "0.2.0")

    def test_help_documents_exit_codes_and_observation_limits(self):
        run = subprocess.run([sys.executable, "-B", str(SCRIPT), "--help"], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(run.returncode, 0)
        help_text = " ".join(run.stdout.split())
        for phrase in ("Exit codes:", "2 = invalid input", "not an atomic snapshot", "No claim"):
            self.assertIn(phrase, help_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
