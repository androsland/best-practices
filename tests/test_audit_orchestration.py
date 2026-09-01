import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "skills/best-practices-audit/scripts/repository_inventory.py"
GUARD = ROOT / "skills/best-practices-audit/scripts/workspace_guard.py"
CATALOG_QUERY = ROOT / "skills/best-practices-catalog/scripts/catalog_query.py"
CATALOG = ROOT / "knowledge/practices.json"


def run_json(*args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, *args], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


class RepositoryInventoryTests(unittest.TestCase):
    def test_inventory_is_navigation_not_a_verdict_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/firstValue.ts").write_text("export const firstValue = 1;\n")
            (root / "TODOS-DONE.md").write_text("No webhook was implemented.\n")
            (root / "package.json").write_text('{"dependencies":{"next":"1.0.0"}}')
            (root / ".temp").mkdir()
            (root / ".temp/linked-project.json").write_text('{"organization_id":"provider-metadata"}')
            result = run_json(str(INVENTORY), str(root), "--format", "json")

        self.assertIsNone(result["outcomes"])
        self.assertIsNone(result["verdict"])
        self.assertNotIn("findings", result)
        self.assertNotIn("surfaces", result)
        paths = {item["path"] for item in result["candidate_files"]}
        self.assertIn("TODOS-DONE.md", paths)
        self.assertIn("src/firstValue.ts", paths)
        self.assertNotIn(".temp/linked-project.json", paths)
        self.assertEqual(result["purpose"], "candidate repository inventory; no applicability or adherence conclusions")

    def test_inventory_reports_bounded_skips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large.md").write_text("x" * 101)
            result = run_json(
                str(INVENTORY), str(root), "--format", "json", "--max-file-bytes", "100"
            )
        self.assertEqual(result["budget"]["skipped_files"], 1)
        self.assertEqual(result["skipped"][0]["reason"], "file-byte-limit")


class WorkspaceGuardTests(unittest.TestCase):
    def init_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.test"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
        (root / "tracked.txt").write_text("before\n")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)

    def test_guard_accepts_unchanged_dirty_state_and_detects_later_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            self.init_repo(root)
            (root / "existing-untracked.txt").write_text("owned by user\n")
            before = run_json(str(GUARD), "snapshot", str(root))
            snapshot_file = Path(directory) / "before.json"
            snapshot_file.write_text(json.dumps(before))

            unchanged = subprocess.run(
                [sys.executable, str(GUARD), "check", str(root), str(snapshot_file)],
                capture_output=True, text=True,
            )
            self.assertEqual(unchanged.returncode, 0)
            self.assertTrue(json.loads(unchanged.stdout)["unchanged"])

            (root / "existing-untracked.txt").write_text("reviewer changed it\n")
            changed = subprocess.run(
                [sys.executable, str(GUARD), "check", str(root), str(snapshot_file)],
                capture_output=True, text=True,
            )
            self.assertEqual(changed.returncode, 3)
            result = json.loads(changed.stdout)
            self.assertFalse(result["unchanged"])
            self.assertIn("untracked_sha256", result["changed_fields"])


class CatalogRoutingTests(unittest.TestCase):
    def test_packets_account_for_every_catalog_practice_once(self):
        summary = run_json(str(CATALOG_QUERY), str(CATALOG), "summary")
        catalog = json.loads(CATALOG.read_text())
        expected = {item["id"] for item in catalog["practices"]}
        seen: list[str] = []
        for reviewer in summary["reviewer_packets"]:
            packet = run_json(
                str(CATALOG_QUERY), str(CATALOG), "packet", "--reviewer", reviewer
            )
            self.assertEqual(len(packet["practices"]), summary["reviewer_packets"][reviewer])
            seen.extend(item["id"] for item in packet["practices"])
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), expected)
        self.assertEqual(summary["practice_count"], len(expected))
        self.assertEqual(len(summary["catalog_sha256"]), 64)

    def test_catalog_list_preserves_provenance_and_maturity(self):
        result = run_json(
            str(CATALOG_QUERY), str(CATALOG), "list", "--domain", "multitenancy"
        )
        self.assertTrue(result["practices"])
        for practice in result["practices"]:
            self.assertIn("enforcement_state", practice)
            self.assertIn("source_video_ids", practice)
            self.assertIn("authoritative_references", practice)
            self.assertIn("revisions", practice)

    def test_coverage_command_rejects_missing_and_accepts_complete_results(self):
        catalog = json.loads(CATALOG.read_text())
        complete = {
            "practice_results": [
                {
                    "practice_id": item["id"],
                    "title": item["title"],
                    "domain": item["domain"],
                    "knowledge_state": item["enforcement_state"],
                    "outcome": "NOT_APPLICABLE",
                    "priority": "INFO",
                    "confidence": "HIGH",
                    "evidence_paths": ["README.md:1"],
                    "applicable_scope": "The mapped repository surface",
                    "project_behavior": "The mapped surface is absent.",
                    "reasoning": "The practice does not apply to the mapped project.",
                    "coverage": "Inspected the repository map.",
                    "remediation": "Reassess if the surface is introduced.",
                    "source_video_ids": item["source_video_ids"],
                    "authoritative_urls": item["authoritative_references"],
                }
                for item in catalog["practices"]
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "results.json"
            results.write_text(json.dumps(complete))
            accepted = subprocess.run(
                [sys.executable, str(CATALOG_QUERY), str(CATALOG), "coverage", str(results)],
                capture_output=True, text=True,
            )
            self.assertEqual(accepted.returncode, 0)
            self.assertTrue(json.loads(accepted.stdout)["complete"])

            security_domains = {"application-security", "multitenancy"}
            packet = {
                "practice_results": [
                    item for item in complete["practice_results"]
                    if item["domain"] in security_domains
                ]
            }
            results.write_text(json.dumps(packet))
            packet_accepted = subprocess.run(
                [
                    sys.executable, str(CATALOG_QUERY), str(CATALOG), "coverage", str(results),
                    "--reviewer", "application-security",
                ],
                capture_output=True, text=True,
            )
            packet_output = json.loads(packet_accepted.stdout)
            self.assertEqual(packet_accepted.returncode, 0)
            self.assertEqual(packet_output["coverage_scope"], "application-security")
            self.assertEqual(packet_output["expected_results"], len(packet["practice_results"]))

            complete["practice_results"][0].pop("reasoning")
            results.write_text(json.dumps(complete))
            malformed = subprocess.run(
                [sys.executable, str(CATALOG_QUERY), str(CATALOG), "coverage", str(results)],
                capture_output=True, text=True,
            )
            self.assertEqual(malformed.returncode, 3)
            self.assertIn(
                complete["practice_results"][0]["practice_id"],
                json.loads(malformed.stdout)["invalid_result_practice_ids"],
            )
            complete["practice_results"][0]["reasoning"] = "The practice does not apply to the mapped project."

            complete["practice_results"].pop()
            results.write_text(json.dumps(complete))
            rejected = subprocess.run(
                [sys.executable, str(CATALOG_QUERY), str(CATALOG), "coverage", str(results)],
                capture_output=True, text=True,
            )
            self.assertEqual(rejected.returncode, 3)
            self.assertFalse(json.loads(rejected.stdout)["complete"])


class OrchestrationContractTests(unittest.TestCase):
    def test_audit_skill_uses_agents_and_not_the_removed_verdict_analyzer(self):
        text = (ROOT / "skills/best-practices-audit/SKILL.md").read_text()
        self.assertIn("project mapper", text.lower())
        self.assertIn("verification reviewer", text.lower())
        self.assertIn("any practice in its packet may apply", text)
        self.assertIn('model: "gpt-5.6-terra"', text)
        self.assertIn('reasoning_effort: "medium"', text)
        self.assertNotIn("audit_evidence.py", text)
        self.assertFalse((ROOT / "skills/best-practices-audit/scripts/audit_evidence.py").exists())

    def test_audit_has_a_consent_and_minimization_gate_before_model_reviewers(self):
        skill = (ROOT / "skills/best-practices-audit/SKILL.md").read_text()
        boundary = (ROOT / "references/model-data-boundary.md").read_text()
        contract = (ROOT / "references/reviewer-contract.md").read_text()
        mapper = (ROOT / "agents/project-mapper.md").read_text()
        verifier = (ROOT / "agents/verification-reviewer.md").read_text()

        self.assertLess(skill.index("## Model data preflight"), skill.index("## Map, route, and review"))
        for phrase in (
            "hard launch gate",
            "retention/training posture",
            "invocation-specific user confirmation",
            "model_input_plan",
            "minimum-necessary",
        ):
            self.assertIn(phrase, skill)
        self.assertIn("Always exclude credential values", boundary)
        self.assertIn("The original request for an audit is not consent", boundary)
        self.assertIn("must not rescan the whole repository", boundary)
        self.assertIn("strict allowlist", contract)
        self.assertIn("If the plan is absent", contract)
        self.assertIn("Refuse to inspect the target if `model_input_plan` is absent", mapper)
        self.assertIn("Do not start a whole-repository search", verifier)

    def test_reviewer_agents_pin_sonnet_medium_and_are_read_only(self):
        agents = sorted((ROOT / "agents").glob("*.md"))
        self.assertGreaterEqual(len(agents), 9)
        for agent in agents:
            text = agent.read_text()
            self.assertIn("model: sonnet", text, agent.name)
            self.assertIn("effort: medium", text, agent.name)
            tools_line = next(line for line in text.splitlines() if line.startswith("tools:"))
            self.assertNotIn("Edit", tools_line, agent.name)
            self.assertNotIn("Write", tools_line, agent.name)

    def test_report_contract_prioritizes_two_evidence_lists(self):
        text = (ROOT / "references/reporting-contract.md").read_text()
        self.assertIn("Where the project diverges", text)
        self.assertIn("Where the project aligns", text)
        self.assertIn("catalog SHA-256", text)
        self.assertNotIn("overall verdict is", text.lower())


if __name__ == "__main__":
    unittest.main()
