#!/usr/bin/env python3
"""Meaningful synthetic checks for no-overwrite, no-false-pass and Git provenance."""
from __future__ import annotations
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_evidence import validate
from file_ops import checked_root, create_planned, plan_files, safe_path

SCRIPTS = Path(__file__).resolve().parent
HEAD = "a" * 40
BASE = "b" * 40

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="engineering-skill-check-")
        self.root = Path(self.tmp.name)
        (self.root / "observed.txt").write_text("actual synthetic observation\n", encoding="utf-8")
        self.artifact_hash = hashlib.sha256((self.root / "observed.txt").read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self):
        return {
            "schema_version": 1, "change_id": "SYNTHETIC-1", "risk": "R2",
            "base_sha": BASE, "head_sha": HEAD, "source_state": "clean", "diff_sha256": None,
            "environment": {"name": "synthetic", "identity": "isolated-fixture-v1"},
            "required_ac": ["AC-01"], "required_checks": ["contract"],
            "checks": [{"id": "contract", "ac": ["AC-01"], "layer": "contract",
                        "status": "PASS", "head_sha": HEAD,
                        "command": ["python3", "-m", "unittest"], "exit_code": 0,
                        "summary": "Synthetic evidence fixture, not business execution.",
                        "artifacts": [{"path": "observed.txt", "sha256": self.artifact_hash}],
                        "collected": 1, "executed": 1, "skipped": 0}],
            "verdict": "PASS", "limitations": []
        }

    def check(self, data):
        return validate(data, self.root, HEAD)

    def cli(self, filename, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / filename), *args],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    def test_matching_local_evidence_is_structurally_valid(self):
        self.assertTrue(self.check(self.manifest())["structurally_valid"])

    def test_blocked_required_check_cannot_be_pass(self):
        data = self.manifest()
        data["checks"][0]["status"] = "BLOCKED"
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_empty_test_run_cannot_be_pass(self):
        data = self.manifest()
        data["checks"][0].update(collected=0, executed=0)
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_required_skip_cannot_be_pass(self):
        data = self.manifest()
        data["checks"][0].update(status="SKIP", skip_reason="Dependency unavailable")
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_nonzero_command_cannot_be_pass(self):
        data = self.manifest()
        data["checks"][0]["exit_code"] = 1
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_boolean_exit_code_is_not_integer_zero(self):
        data = self.manifest()
        data["checks"][0]["exit_code"] = False
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_candidate_mismatch_is_rejected(self):
        data = self.manifest()
        data["head_sha"] = "c" * 40
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_old_check_head_is_rejected(self):
        data = self.manifest()
        data["checks"][0]["head_sha"] = BASE
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_missing_ac_coverage_is_rejected(self):
        data = self.manifest()
        data["required_ac"].append("AC-02")
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_duplicate_check_id_is_rejected(self):
        data = self.manifest()
        data["checks"].append(copy.deepcopy(data["checks"][0]))
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_missing_required_check_is_rejected(self):
        data = self.manifest()
        data["required_checks"].append("browser")
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_changed_artifact_is_rejected(self):
        (self.root / "observed.txt").write_text("changed after verification", encoding="utf-8")
        self.assertFalse(self.check(self.manifest())["structurally_valid"])

    def test_artifact_path_traversal_is_rejected(self):
        data = self.manifest()
        data["checks"][0]["artifacts"][0]["path"] = "../outside.txt"
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_symlinked_artifact_is_rejected(self):
        (self.root / "alias.txt").symlink_to(self.root / "observed.txt")
        data = self.manifest()
        data["checks"][0]["artifacts"][0]["path"] = "alias.txt"
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_external_artifact_is_explicitly_unverified(self):
        data = self.manifest()
        data["checks"][0]["artifacts"] = [{"url": "https://example.invalid/immutable/123",
                                          "sha256": self.artifact_hash}]
        result = self.check(data)
        self.assertTrue(result["structurally_valid"])
        self.assertTrue(any("not fetched" in x for x in result["warnings"]))

    def test_dirty_source_is_not_final_pass(self):
        data = self.manifest()
        data["source_state"] = "dirty"
        data["diff_sha256"] = "d" * 64
        self.assertFalse(self.check(data)["structurally_valid"])

    def test_unknown_field_types_do_not_crash(self):
        for field in ("risk", "source_state", "verdict"):
            data = self.manifest()
            data[field] = []
            self.assertFalse(self.check(data)["structurally_valid"])
        for field in ("status", "layer"):
            data = self.manifest()
            data["checks"][0][field] = {}
            self.assertFalse(self.check(data)["structurally_valid"])

    def test_blocked_manifest_is_valid_but_require_pass_exits_three(self):
        data = self.manifest()
        data["verdict"] = "BLOCKED"
        data["checks"][0]["status"] = "BLOCKED"
        data["limitations"] = ["Environment unavailable"]
        (self.root / "evidence.json").write_text(json.dumps(data), encoding="utf-8")
        result = self.cli("check_evidence.py", "--root", str(self.root), "--file", "evidence.json", "--require-pass")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_bootstrap_default_is_preview(self):
        target = self.root / "project"
        result = self.cli("bootstrap_project.py", "--root", str(target), "--name", "Synthetic")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(target.exists())

    def test_bootstrap_apply_is_idempotent_and_name_is_json_safe(self):
        target = self.root / "project"
        args = ("--root", str(target), "--name", 'Name with "quotes"', "--date", "2026-11-04", "--apply")
        first = self.cli("bootstrap_project.py", *args)
        second = self.cli("bootstrap_project.py", *args)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(json.loads(second.stdout)["created"], [])
        config = json.loads((target / ".engineering/project.json").read_text(encoding="utf-8"))
        self.assertEqual(config["project_name"], 'Name with "quotes"')
        self.assertIsNone(config["commands"]["e2e"])

    def test_bootstrap_conflict_preserves_all_existing_files(self):
        target = self.root / "project"
        target.mkdir()
        (target / "README.md").write_text("User content", encoding="utf-8")
        result = self.cli("bootstrap_project.py", "--root", str(target), "--name", "Synthetic", "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "User content")
        self.assertFalse((target / "AGENTS.md").exists())

    def test_symlinked_parent_write_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "redirect").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            plan_files(self.root, {"redirect/data.txt": b"payload"})

    def test_planned_write_does_not_overwrite_new_racing_file(self):
        files = {"fresh.txt": b"expected"}
        plan = plan_files(self.root, files)
        (self.root / "fresh.txt").write_text("other worker", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            create_planned(self.root, files, plan)
        self.assertEqual((self.root / "fresh.txt").read_text(encoding="utf-8"), "other worker")

    def test_export_preview_does_not_write(self):
        target = self.root / "project"
        result = self.cli("export_skill.py", "--root", str(target), "--target", "both")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)["plan"]
        self.assertTrue(any(x["path"].startswith(".agents/skills/") for x in plan))
        self.assertTrue(any(x["path"].startswith(".claude/skills/") for x in plan))
        self.assertFalse(target.exists())

    def test_repo_snapshot_records_candidate_without_mutating(self):
        target = self.root / "repo"
        target.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(target), *args], check=True, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
        git("init", "-q")
        git("config", "user.name", "Synthetic")
        git("config", "user.email", "synthetic@example.invalid")
        (target / "code.txt").write_text("one\n", encoding="utf-8")
        git("add", "code.txt")
        git("commit", "-qm", "base")
        base = git("rev-parse", "HEAD")
        (target / "code.txt").write_text("two\n", encoding="utf-8")
        git("add", "code.txt")
        git("commit", "-qm", "change")
        head = git("rev-parse", "HEAD")
        before = git("status", "--porcelain")
        result = self.cli("repo_snapshot.py", "--repo", str(target), "--base", base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["head_sha"], head)
        self.assertEqual(value["base_sha"], base)
        self.assertFalse(value["range_empty"])
        self.assertEqual(git("status", "--porcelain"), before)
        self.assertEqual(git("rev-parse", "HEAD"), head)
        (target / "code.txt").write_text("unstaged change\n", encoding="utf-8")
        dirty = self.cli("repo_snapshot.py", "--repo", str(target))
        self.assertEqual(dirty.returncode, 0, dirty.stdout + dirty.stderr)
        self.assertEqual(json.loads(dirty.stdout)["status"], [" M code.txt"])
        self.assertEqual((target / "code.txt").read_text(encoding="utf-8"), "unstaged change\n")

    def test_repo_snapshot_does_not_execute_fsmonitor_hook(self):
        target = self.root / "repo-hook"
        target.mkdir()
        def git(*args):
            return subprocess.run(["git", "-C", str(target), *args], check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git("init", "-q")
        git("config", "user.name", "Synthetic")
        git("config", "user.email", "synthetic@example.invalid")
        (target / "code.txt").write_text("one\n", encoding="utf-8")
        git("add", "code.txt")
        git("commit", "-qm", "base")
        marker = self.root / "hook-executed"
        hook = self.root / "fsmonitor.sh"
        hook.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nprintf "token\\0"\n', encoding="utf-8")
        hook.chmod(0o700)
        git("config", "core.fsmonitor", str(hook))
        result = self.cli("repo_snapshot.py", "--repo", str(target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(marker.exists(), "Read-only snapshot executed repository-configured hook")

if __name__ == "__main__":
    unittest.main(verbosity=2)
