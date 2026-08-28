import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "skills/project-practices-curator/scripts/collect_instagram.py"
STATE = ROOT / "skills/project-practices-curator/scripts/curation_state.py"


class InstagramCollectorTests(unittest.TestCase):
    def test_dependency_preflight_detects_missing_and_offers_install(self):
        env = os.environ.copy()
        env["PATH"] = "/definitely-missing"
        completed = subprocess.run(
            [sys.executable, str(COLLECTOR), "--check-dependencies"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        result = json.loads(completed.stdout)
        dependency = result["dependencies"]["gallery-dl"]
        self.assertFalse(dependency["installed"])
        self.assertTrue(dependency["install_options"])
        self.assertEqual(sum(bool(option["recommended"]) for option in dependency["install_options"]), 1)
        self.assertTrue(all(option["requires_explicit_approval"] for option in dependency["install_options"]))
        self.assertIn("ask the user", result["next_step"].lower())

    def test_live_collection_missing_dependency_fails_closed_with_exit_three(self):
        env = os.environ.copy()
        env["PATH"] = "/definitely-missing"
        completed = subprocess.run(
            [sys.executable, str(COLLECTOR), "https://www.instagram.com/example/", "--dry-run"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(completed.returncode, 3)
        result = json.loads(completed.stdout)
        self.assertEqual(result["error"]["code"], "DEPENDENCY_MISSING")
        self.assertFalse(result["dependency"]["installed"])
        self.assertIn("do not install automatically", result["next_step"].lower())

    def test_dependency_preflight_reports_installed_version(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "gallery-dl"
            executable.write_text("#!/bin/sh\necho 9.9.9-fixture\n")
            executable.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = directory
            completed = subprocess.run(
                [sys.executable, str(COLLECTOR), "--check-dependencies"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        dependency = json.loads(completed.stdout)["dependencies"]["gallery-dl"]
        self.assertTrue(dependency["installed"])
        self.assertEqual(dependency["version"], "9.9.9-fixture")
        self.assertEqual(dependency["install_options"], [])

    def test_new_only_limit_and_dates_use_stable_ids(self):
        completed = subprocess.run(
            [
                sys.executable, str(COLLECTOR), "https://www.instagram.com/practice_creator/",
                "--enumeration-file", str(ROOT / "fixtures/instagram/enumeration.json"),
                "--state", str(ROOT / "fixtures/instagram/state.json"),
                "--new-only", "--after", "2026-01-01", "--limit", "1", "--dry-run",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["selected"][0]["source_id"], "instagram:NEWEST01")
        self.assertFalse(result["browser_cookie_consent"])
        self.assertIn("--config-ignore", result["enumeration_command"])

    def test_browser_cookie_access_requires_explicit_same_invocation_consent(self):
        completed = subprocess.run(
            [sys.executable, str(COLLECTOR), "https://www.instagram.com/example/", "--cookies-from-browser", "firefox", "--dry-run"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("requires --consent-browser-cookies", completed.stderr)

    def test_cookie_file_path_is_redacted_from_plan(self):
        completed = subprocess.run(
            [
                sys.executable, str(COLLECTOR), "https://www.instagram.com/example/",
                "--enumeration-file", str(ROOT / "fixtures/instagram/enumeration.json"),
                "--cookies", "/sensitive/session/cookies.txt", "--dry-run",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertNotIn("/sensitive/session/cookies.txt", completed.stdout)
        self.assertIn("<offline-enumeration>", completed.stdout)
        self.assertIn("<redacted-cookie-file>", completed.stdout)


class CurationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.catalog = Path(self.temp.name) / "practices.json"
        shutil.copyfile(ROOT / "knowledge/practices.json", self.catalog)

    def tearDown(self):
        self.temp.cleanup()

    def run_state(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(STATE), *args], check=check, capture_output=True, text=True)

    def test_catalog_validates(self):
        completed = self.run_state("validate", str(self.catalog))
        self.assertIn("valid catalog", completed.stdout)

    def test_local_media_id_is_content_based(self):
        media = Path(self.temp.name) / "clip.mp4"
        media.write_bytes(b"fixture-video-bytes")
        completed = self.run_state("source-id", str(media))
        expected = hashlib.sha256(b"fixture-video-bytes").hexdigest()
        self.assertEqual(completed.stdout.strip(), f"local-sha256:{expected}")

    def test_new_video_claim_can_only_enter_as_candidate_or_advisory(self):
        completed = self.run_state(
            "propose", str(self.catalog),
            "--practice-id", "practice.example.video-claim",
            "--domain", "coding-ai", "--title", "Video claim", "--statement", "A bounded candidate.",
            "--classification", "new", "--enforcement-state", "candidate",
            "--applicability", "Example projects", "--signal", "example.yml", "--confidence", "LOW",
            "--source-id", "instagram:NEWEST01", "--reason", "New video claim pending review.",
        )
        self.assertIn("created candidate/advisory", completed.stdout)
        data = json.loads(self.catalog.read_text())
        practice = next(item for item in data["practices"] if item["id"] == "practice.example.video-claim")
        self.assertEqual(practice["enforcement_state"], "candidate")

        rejected = self.run_state(
            "propose", str(self.catalog),
            "--practice-id", "practice.example.direct-rule", "--domain", "coding-ai",
            "--title", "Bad direct rule", "--statement", "Should be rejected.",
            "--classification", "new", "--enforcement-state", "enforceable",
            "--applicability", "All", "--source-id", "instagram:X", "--reason", "No gate.",
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)

    def test_consequential_claim_needs_current_primary_reference(self):
        completed = self.run_state(
            "propose", str(self.catalog),
            "--practice-id", "practice.security.unverified-video", "--domain", "application-security",
            "--title", "Unverified", "--statement", "A security claim.", "--classification", "new",
            "--applicability", "Web apps", "--source-id", "instagram:SECURITY", "--reason", "Video only.",
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("require --authoritative-ref and --verified-on", completed.stderr)

    def test_promotion_is_separate_and_requires_behavioral_evidence(self):
        self.run_state(
            "propose", str(self.catalog),
            "--practice-id", "practice.example.promotable", "--domain", "coding-ai",
            "--title", "Promotable", "--statement", "Objective candidate.", "--classification", "new",
            "--applicability", "Code projects", "--signal", "project.yml", "--source-id", "local-sha256:abc",
            "--reason", "Initial candidate.",
        )
        rejected = self.run_state(
            "promote", str(self.catalog), "--practice-id", "practice.example.promotable",
            "--reviewed", "--verified-on", "2026-08-28", "--test-evidence", "pass fixture",
            "--reason", "Insufficient tests.", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("at least three", rejected.stderr)

        self.run_state(
            "promote", str(self.catalog), "--practice-id", "practice.example.promotable",
            "--reviewed", "--verified-on", "2026-08-28",
            "--test-evidence", "pass fixture", "--test-evidence", "partial fixture", "--test-evidence", "not-applicable fixture",
            "--reason", "Reviewed objective evidence.",
        )
        data = json.loads(self.catalog.read_text())
        practice = next(item for item in data["practices"] if item["id"] == "practice.example.promotable")
        self.assertEqual(practice["enforcement_state"], "enforceable")
        self.assertEqual(practice["revisions"][-1]["change"], "promoted-to-enforceable-after-review")


if __name__ == "__main__":
    unittest.main()
