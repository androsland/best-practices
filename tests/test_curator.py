import json
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "skills/project-practices-curator/scripts/collect_instagram.py"
STATE = ROOT / "skills/project-practices-curator/scripts/curation_state.py"

COLLECTOR_SPEC = importlib.util.spec_from_file_location(
    "project_practices_collect_instagram", COLLECTOR
)
assert COLLECTOR_SPEC and COLLECTOR_SPEC.loader
COLLECTOR_MODULE = importlib.util.module_from_spec(COLLECTOR_SPEC)
COLLECTOR_SPEC.loader.exec_module(COLLECTOR_MODULE)

STATE_SPEC = importlib.util.spec_from_file_location("project_practices_curation_state", STATE)
assert STATE_SPEC and STATE_SPEC.loader
STATE_MODULE = importlib.util.module_from_spec(STATE_SPEC)
STATE_SPEC.loader.exec_module(STATE_MODULE)


class InstagramCollectorTests(unittest.TestCase):
    def fake_gallery_environment(self, directory: str, mode: str) -> tuple[dict, Path]:
        executable = Path(directory) / "gallery-dl"
        executable.write_text(
            """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("1.32.9")
    raise SystemExit(0)

Path(os.environ["FAKE_GALLERY_ARGS"]).write_text(json.dumps(sys.argv[1:]))
mode = os.environ["FAKE_GALLERY_MODE"]
if mode == "failure":
    print("failed using /sensitive/session/cookies.txt and firefox", file=sys.stderr)
    raise SystemExit(7)

records = [
    {"shortcode": "LIVE02", "date": "2026-08-02", "username": "fixture"},
    {"shortcode": "LIVE01", "date": "2026-08-01", "username": "fixture"},
]
if mode == "array":
    print(json.dumps(records))
else:
    for record in records:
        print(json.dumps(record))
"""
        )
        executable.chmod(0o755)
        args_path = Path(directory) / "args.json"
        env = os.environ.copy()
        env["PATH"] = directory + os.pathsep + env.get("PATH", "")
        env["FAKE_GALLERY_ARGS"] = str(args_path)
        env["FAKE_GALLERY_MODE"] = mode
        return env, args_path

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
        self.assertTrue(
            all("gallery-dl==1.32.9" in option["command"] for option in dependency["install_options"])
        )
        self.assertIn("ask the user", result["next_step"].lower())

    def test_live_collection_missing_dependency_fails_closed_with_exit_three(self):
        env = os.environ.copy()
        env["PATH"] = "/definitely-missing"
        completed = subprocess.run(
            [sys.executable, str(COLLECTOR), "https://www.instagram.com/example/"],
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
            executable.write_text("#!/bin/sh\necho 1.32.9\n")
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
        self.assertEqual(dependency["version"], "1.32.9")
        self.assertTrue(dependency["ready"])
        self.assertEqual(dependency["install_options"], [])

    def test_live_collection_rejects_unreviewed_installed_version(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "gallery-dl"
            executable.write_text("#!/bin/sh\necho 9.9.9-unreviewed\n")
            executable.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = directory
            completed = subprocess.run(
                [sys.executable, str(COLLECTOR), "https://www.instagram.com/example/"],
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertEqual(completed.returncode, 3)
        result = json.loads(completed.stdout)
        self.assertEqual(result["error"]["code"], "DEPENDENCY_VERSION_MISMATCH")
        self.assertFalse(result["dependency"]["ready"])
        self.assertTrue(result["dependency"]["install_options"])

    def test_new_only_limit_and_dates_use_stable_ids(self):
        completed = subprocess.run(
            [
                sys.executable, str(COLLECTOR), "https://www.instagram.com/practice_creator/",
                "--enumeration-file", str(ROOT / "fixtures/instagram/enumeration.json"),
                "--state", str(ROOT / "fixtures/instagram/state.json"),
                "--new-only", "--after", "2026-01-01", "--limit", "1",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual(result["selected_count"], 1)
        self.assertEqual(result["selected"][0]["source_id"], "instagram:NEWEST01")
        self.assertFalse(result["browser_cookie_consent"])
        self.assertIn("--config-ignore", result["enumeration_command"])

    def test_browser_cookie_access_requires_explicit_same_invocation_consent(self):
        completed = subprocess.run(
            [sys.executable, str(COLLECTOR), "https://www.instagram.com/example/", "--cookies-from-browser", "firefox"],
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
                "--cookies", "/sensitive/session/cookies.txt",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertNotIn("/sensitive/session/cookies.txt", completed.stdout)
        self.assertIn("<offline-enumeration>", completed.stdout)
        self.assertIn("<redacted-cookie-file>", completed.stdout)

    def test_live_fake_gallery_supports_json_array_and_json_lines(self):
        for mode in ("array", "lines"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                env, _ = self.fake_gallery_environment(directory, mode)
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(COLLECTOR),
                        "https://www.instagram.com/example/",
                        "--limit",
                        "2",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                result = json.loads(completed.stdout)
                self.assertEqual(result["selected_count"], 2)
                self.assertEqual(result["selected"][0]["source_id"], "instagram:LIVE02")

    def test_live_fake_gallery_forwards_consented_browser_args_but_redacts_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            env, args_path = self.fake_gallery_environment(directory, "lines")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(COLLECTOR),
                    "https://www.instagram.com/example/",
                    "--cookies-from-browser",
                    "firefox",
                    "--consent-browser-cookies",
                    "--limit",
                    "1",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            forwarded = json.loads(args_path.read_text())
            result = json.loads(completed.stdout)
            self.assertIn("--cookies-from-browser", forwarded)
            self.assertIn("firefox", forwarded)
            self.assertNotIn("firefox", json.dumps(result["enumeration_command"]))
            self.assertIn("<consented-browser-profile>", result["enumeration_command"])

    def test_live_failure_redacts_cookie_and_browser_details(self):
        with tempfile.TemporaryDirectory() as directory:
            env, _ = self.fake_gallery_environment(directory, "failure")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(COLLECTOR),
                    "https://www.instagram.com/example/",
                    "--cookies",
                    "/sensitive/session/cookies.txt",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertNotIn("/sensitive/session/cookies.txt", completed.stderr)
            self.assertIn("<redacted-cookie-file>", completed.stderr)

    def test_limit_and_offline_file_size_are_bounded(self):
        rejected_limit = subprocess.run(
            [
                sys.executable,
                str(COLLECTOR),
                "https://www.instagram.com/example/",
                "--limit",
                "501",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(rejected_limit.returncode, 0)
        self.assertIn("must not exceed 500", rejected_limit.stderr)

        with tempfile.TemporaryDirectory() as directory:
            oversized = Path(directory) / "enumeration.json"
            oversized.write_text(" " * 5_000_001)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(COLLECTOR),
                    "https://www.instagram.com/example/",
                    "--enumeration-file",
                    str(oversized),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("split it into a smaller JSON/JSON-lines batch", completed.stderr)

    def test_bounded_process_rejects_excess_output_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            noisy = Path(directory) / "noisy.py"
            noisy.write_text("import sys\nsys.stdout.write('x' * 4096)\n")
            with self.assertRaises(COLLECTOR_MODULE.BoundedProcessError):
                COLLECTOR_MODULE.run_bounded(
                    [sys.executable, str(noisy)],
                    stdout_limit=32,
                    stderr_limit=32,
                    timeout_seconds=1,
                )

            stalled = Path(directory) / "stalled.py"
            stalled.write_text("import time\ntime.sleep(10)\n")
            with mock.patch.object(
                COLLECTOR_MODULE, "PROCESS_TERMINATION_GRACE_SECONDS", 0.1
            ):
                with self.assertRaises(COLLECTOR_MODULE.BoundedProcessError):
                    COLLECTOR_MODULE.run_bounded(
                        [sys.executable, str(stalled)],
                        stdout_limit=32,
                        stderr_limit=32,
                        timeout_seconds=0.1,
                    )


class CurationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.catalog = Path(self.temp.name) / "practices.json"
        shutil.copyfile(ROOT / "knowledge/practices.json", self.catalog)

    def tearDown(self):
        self.temp.cleanup()

    def run_state(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(STATE), *args], check=check, capture_output=True, text=True)

    def proposal_arguments(self) -> list[str]:
        return [
            "propose",
            str(self.catalog),
            "--practice-id",
            "practice.example.model-output",
            "--domain",
            "coding-ai",
            "--title",
            "Bounded model output",
            "--statement",
            "A reviewable candidate statement.",
            "--classification",
            "new",
            "--applicability",
            "Code projects",
            "--signal",
            "project.yml",
            "--source-id",
            "instagram:MODEL01",
            "--reason",
            "Extracted with timestamped evidence.",
        ]

    @staticmethod
    def replace_argument(arguments: list[str], flag: str, value: str) -> list[str]:
        updated = list(arguments)
        updated[updated.index(flag) + 1] = value
        return updated

    def test_catalog_validates(self):
        completed = self.run_state("validate", str(self.catalog))
        self.assertIn("valid catalog", completed.stdout)

    def test_local_media_id_is_content_based(self):
        media = Path(self.temp.name) / "clip.mp4"
        media.write_bytes(b"fixture-video-bytes")
        completed = self.run_state("source-id", str(media))
        expected = hashlib.sha256(b"fixture-video-bytes").hexdigest()
        self.assertEqual(completed.stdout.strip(), f"local-sha256:{expected}")

    def test_state_init_overwrite_and_incremental_recording(self):
        state = Path(self.temp.name) / "state.json"
        self.run_state("init-state", str(state))
        original = state.read_bytes()
        rejected = self.run_state("init-state", str(state), check=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(state.read_bytes(), original)

        self.run_state(
            "record-source",
            str(state),
            "--source-id",
            "instagram:STATE01",
            "--url",
            "https://www.instagram.com/reel/STATE01/",
            "--status",
            "failed",
            "--claim-id",
            "claim-a",
            "--evidence-type",
            "metadata-only",
        )
        self.run_state(
            "record-source",
            str(state),
            "--source-id",
            "instagram:STATE01",
            "--url",
            "https://www.instagram.com/reel/STATE01/",
            "--status",
            "processed",
            "--claim-id",
            "claim-a",
            "--claim-id",
            "claim-b",
            "--evidence-type",
            "transcript-and-frames",
        )
        record = json.loads(state.read_text())["processed_sources"]["instagram:STATE01"]
        self.assertEqual(record["attempts"], 2)
        self.assertEqual(record["status"], "processed")
        self.assertEqual(record["claim_ids"], ["claim-a", "claim-b"])

        before_failure = state.read_bytes()
        failed = self.run_state(
            "record-source",
            str(state),
            "--source-id",
            "instagram:STATE02",
            "--url",
            "https://www.instagram.com/reel/STATE02/",
            "--status",
            "skipped",
            "--processed-at",
            "not-a-date",
            "--evidence-type",
            "metadata-only",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(state.read_bytes(), before_failure)

        self.run_state("init-state", str(state), "--force")
        self.assertEqual(json.loads(state.read_text())["processed_sources"], {})

    def test_record_source_supports_every_status(self):
        state = Path(self.temp.name) / "statuses.json"
        for status in ("processed", "failed", "skipped"):
            self.run_state(
                "record-source",
                str(state),
                "--source-id",
                f"instagram:{status.upper()}",
                "--url",
                f"https://www.instagram.com/reel/{status.upper()}/",
                "--status",
                status,
                "--evidence-type",
                "metadata-only",
            )
        records = json.loads(state.read_text())["processed_sources"]
        self.assertEqual({record["status"] for record in records.values()}, {"processed", "failed", "skipped"})

    def test_atomic_write_failure_preserves_valid_state(self):
        state = Path(self.temp.name) / "atomic-state.json"
        original = {"schema_version": 1, "updated_at": "2026-08-29", "processed_sources": {}}
        state.write_text(json.dumps(original))

        with mock.patch.object(STATE_MODULE.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                STATE_MODULE.atomic_write(
                    state,
                    {"schema_version": 1, "updated_at": "2026-08-30", "processed_sources": {"x": {}}},
                )

        self.assertEqual(json.loads(state.read_text()), original)
        self.assertEqual(list(state.parent.glob(f".{state.name}.*")), [])

    def test_adversarial_model_output_is_rejected_without_catalog_changes(self):
        corpus = json.loads(
            (ROOT / "fixtures/curator/model-output-cases.json").read_text()
        )
        self.assertEqual(corpus["prompt_version"], "curator-claim-extraction-v1")
        original = self.catalog.read_bytes()
        for case in corpus["cases"]:
            with self.subTest(case=case["id"]):
                value = case.get("value")
                if value is None:
                    repeat = case["repeat"]
                    value = repeat["character"] * repeat["count"]
                arguments = self.replace_argument(
                    self.proposal_arguments(), f"--{case['field']}", value
                )
                completed = self.run_state(*arguments, check=False)
                self.assertEqual(case["expected"], "reject")
                self.assertEqual(completed.returncode, 2)
                self.assertIn("proposal rejected", completed.stderr)
                self.assertEqual(self.catalog.read_bytes(), original)

    def test_reference_urls_fail_closed_on_credentials_and_local_targets(self):
        original = self.catalog.read_bytes()
        for url in (
            "https://user:password@example.com/reference",
            "https://127.0.0.1/reference",
            "https://localhost/reference",
        ):
            with self.subTest(url=url):
                completed = self.run_state(
                    *self.proposal_arguments(),
                    "--authoritative-ref",
                    f"Primary|{url}|Supports the candidate.",
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(self.catalog.read_bytes(), original)

    def test_aggregate_model_output_limit_leaves_catalog_unchanged(self):
        original = self.catalog.read_bytes()
        arguments = self.proposal_arguments()
        for index in range(61):
            arguments.extend(["--signal", f"signal-{index}-" + "x" * 188])
        completed = self.run_state(*arguments, check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("aggregate limit", completed.stderr)
        self.assertEqual(self.catalog.read_bytes(), original)

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

    def test_existing_practice_classifications_append_provenance_without_mutation(self):
        practice_id = "practice.coding.surgical-changes"
        initial = next(
            item
            for item in json.loads(self.catalog.read_text())["practices"]
            if item["id"] == practice_id
        )
        original_statement = initial["statement"]
        original_state = initial["enforcement_state"]
        revision_count = len(initial["revisions"])

        for classification in ("supporting", "conflicting", "obsolete", "promotional"):
            arguments = [
                "propose",
                str(self.catalog),
                "--practice-id",
                practice_id,
                "--domain",
                "coding-ai",
                "--title",
                "Ignored existing title",
                "--statement",
                "This must not replace the reviewed statement.",
                "--classification",
                classification,
                "--applicability",
                "Code projects",
                "--source-id",
                f"instagram:{classification.upper()}",
                "--authoritative-ref",
                "Primary docs|https://example.com/primary|Supports fixture classification behavior.",
                "--verified-on",
                "2026-08-29",
                "--reason",
                f"Recorded {classification} evidence.",
            ]
            if classification == "promotional":
                arguments.extend(["--enforcement-state", "advisory"])
            self.run_state(*arguments)

            practice = next(
                item
                for item in json.loads(self.catalog.read_text())["practices"]
                if item["id"] == practice_id
            )
            revision_count += 1
            self.assertEqual(practice["statement"], original_statement)
            self.assertEqual(practice["enforcement_state"], original_state)
            self.assertEqual(len(practice["revisions"]), revision_count)
            revision = practice["revisions"][-1]
            self.assertEqual(revision["change"], f"video-claim-{classification}")
            self.assertEqual(revision["date"], "2026-08-29")
            self.assertIn("https://example.com/primary", revision["authoritative_urls"])
            self.assertIn(f"instagram:{classification.upper()}", practice["source_video_ids"])

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
