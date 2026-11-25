#!/usr/bin/env python3
"""Synthetic distribution checks: no overwrite, portable policy, complete license and release identity."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_skill import NAME, portable_interface, source_files
from prepare_repository import repository_files

SCRIPTS = Path(__file__).resolve().parent
SOURCE = SCRIPTS.parent


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="skill-distribution-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *args], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    def candidate(self):
        target = self.root / "candidate"
        result = self.cli("prepare_repository.py", "--root", str(target), "--repository", "example/engineering-skills",
                          "--release-ref", "v0.2.0", "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return target

    def validate(self, target, *args):
        return subprocess.run([sys.executable, str(target / "tools/validate_repository.py"), *args],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    def test_interface_export_does_not_copy_managed_policy(self):
        raw = b"interface:\n  display_name: Demo\n  default_prompt: Use it\npolicy:\n  allow_implicit_invocation: true\ndependencies:\n  tools: []\n"
        exported = portable_interface(raw)
        self.assertIn(b"default_prompt: Use it", exported)
        self.assertNotIn(b"policy:", exported)
        self.assertNotIn(b"dependencies:", exported)

    def test_top_level_source_directory_symlink_is_not_exported(self):
        source = self.root / "source"
        source.mkdir()
        (source / "SKILL.md").write_bytes((SOURCE / "SKILL.md").read_bytes())
        (source / "LICENSE.txt").write_bytes((SOURCE / "LICENSE.txt").read_bytes())
        external = self.root / "external"
        external.mkdir()
        (external / "private.txt").write_text("Synthetic external material", encoding="utf-8")
        (source / "references").symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValueError):
            source_files(source)
        with self.assertRaises(ValueError):
            repository_files(source, "example/engineering-skills", "v0.2.0")

    def test_all_export_has_two_targets_license_and_no_managed_policy(self):
        target = self.root / "project"
        result = self.cli("export_skill.py", "--root", str(target), "--target", "all", "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for folder in (".agents", ".claude"):
            installed = target / folder / "skills" / NAME
            self.assertEqual((installed / "LICENSE.txt").read_bytes(), (SOURCE / "LICENSE.txt").read_bytes())
            self.assertNotIn("policy:", (installed / "agents/openai.yaml").read_text(encoding="utf-8"))
        self.assertFalse((target / ".opencode").exists())
        second = self.cli("export_skill.py", "--root", str(target), "--target", "all", "--apply")
        self.assertEqual(json.loads(second.stdout)["created"], [])

    def test_opencode_export_uses_shared_directory(self):
        target = self.root / "project"
        result = self.cli("export_skill.py", "--root", str(target), "--target", "opencode", "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((target / ".agents/skills" / NAME / "SKILL.md").is_file())
        self.assertFalse((target / ".claude").exists())
        self.assertFalse((target / ".opencode").exists())

    def test_export_conflict_does_not_partially_create_other_target(self):
        target = self.root / "project"
        existing = target / ".claude/skills" / NAME
        existing.mkdir(parents=True)
        (existing / "SKILL.md").write_text("User custom skill", encoding="utf-8")
        result = self.cli("export_skill.py", "--root", str(target), "--target", "all", "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertEqual((existing / "SKILL.md").read_text(), "User custom skill")
        self.assertFalse((target / ".agents").exists())

    def test_repository_preview_never_creates_output(self):
        target = self.root / "candidate"
        result = self.cli("prepare_repository.py", "--root", str(target), "--repository", "example/engineering-skills")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(target.exists())
        self.assertFalse(json.loads(result.stdout)["published"])

    def test_candidate_validates_and_tampered_files_do_not(self):
        target = self.candidate()
        result = self.validate(target, "--check-manifest")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((target / ".git").exists())
        changed = target / "skills" / NAME / "SKILL.md"
        changed.write_text(changed.read_text(encoding="utf-8") + "\nReviewed local change.\n", encoding="utf-8")
        result = self.validate(target, "--check-manifest")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Manifest differs", result.stdout)

    def test_manifest_refresh_is_explicit_and_preserves_observed_identity(self):
        target = self.candidate()
        before = json.loads((target / "release-manifest.json").read_text())
        (target / "CHANGELOG.md").write_text("# Changelog\n\nA reviewed edit.\n", encoding="utf-8")
        result = self.validate(target, "--refresh-manifest")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = json.loads((target / "release-manifest.json").read_text())
        self.assertEqual(before["proposed_repository"], after["proposed_repository"])
        self.assertNotEqual(before["files"]["CHANGELOG.md"], after["files"]["CHANGELOG.md"])
        self.assertEqual(self.validate(target, "--check-manifest").returncode, 0)

    def test_missing_license_or_private_marker_fails_validation(self):
        target = self.candidate()
        (target / "skills" / NAME / "LICENSE.txt").unlink()
        # Construct a synthetic marker; never embed a real personal identifier in the package.
        (target / "unexpected.md").write_text("libfile_" + "a" * 32, encoding="utf-8")
        result = self.validate(target)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Missing file", result.stdout)
        self.assertIn("Potential private", result.stdout)
        self.assertNotIn("a" * 32, result.stdout)

    def test_invalid_manifest_shapes_report_json_without_traceback(self):
        target = self.candidate()
        for data in (None, [], "invalid", 42):
            with self.subTest(shape=type(data).__name__):
                (target / "release-manifest.json").write_text(json.dumps(data), encoding="utf-8")
                for mode in ("--check-manifest", "--refresh-manifest"):
                    result = self.validate(target, mode)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("Unsupported manifest structure", json.loads(result.stdout)["errors"])
                    self.assertNotIn("Traceback", result.stderr)

    def test_repository_conflict_preserves_existing_content(self):
        target = self.root / "existing"
        target.mkdir()
        (target / "README.md").write_text("Human text", encoding="utf-8")
        result = self.cli("prepare_repository.py", "--root", str(target), "--repository", "example/engineering-skills", "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(target.iterdir()), [target / "README.md"])
        self.assertEqual((target / "README.md").read_text(), "Human text")

    def test_repository_parameters_reject_command_and_traversal_text(self):
        for repository, ref in (("https://example.invalid/repo", "v1"), ("example/repo;echo", "v1"),
                                ("example/repo", "../outside"), ("example/repo", "$(command)")):
            with self.assertRaises(ValueError):
                repository_files(SOURCE, repository, ref)


if __name__ == "__main__":
    unittest.main(verbosity=2)
