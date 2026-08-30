import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "skills/project-practices-audit/scripts/audit_evidence.py"


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def audit(fixture: str) -> dict:
    target = ROOT / "fixtures" / fixture
    before = tree_digest(target)
    completed = subprocess.run(
        [sys.executable, str(AUDIT), str(target), "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert before == tree_digest(target), "audit modified its target"
    return json.loads(completed.stdout)


def findings_by_id(report: dict) -> dict:
    return {item["check_id"]: item for item in report["findings"]}


def audit_path(root: Path, *extra: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(AUDIT), str(root), "--format", "json", *extra],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class AuditBehaviorTests(unittest.TestCase):
    def test_secure_saas_has_observable_passes(self):
        report = audit("secure-saas")
        findings = findings_by_id(report)
        self.assertTrue(report["read_only"])
        self.assertEqual(report["summary"]["verdict"], "PASS")
        for check_id in (
            "DEV-TEST-001", "DEV-CI-001", "DEV-DEPS-001", "SEC-RLS-001",
            "SEC-WEBHOOK-001", "REL-RPO-001", "REL-RESTORE-001",
            "TEN-ISO-001", "INF-DEPLOY-001", "PROD-VALUE-001",
            "AI-SUPPLY-001", "AI-DATA-001",
        ):
            self.assertEqual(findings[check_id]["status"], "PASS", check_id)

    def test_mixed_saas_exposes_failures_without_overclaiming_authz(self):
        report = audit("mixed-saas")
        findings = findings_by_id(report)
        self.assertEqual(report["summary"]["verdict"], "NEEDS_WORK")
        self.assertEqual(findings["DEV-TEST-001"]["status"], "MISSING")
        self.assertEqual(findings["DEV-DEPS-001"]["status"], "PASS")
        self.assertEqual(findings["SEC-RLS-001"]["status"], "MISSING")
        self.assertEqual(findings["SEC-WEBHOOK-001"]["status"], "MISSING")
        self.assertEqual(findings["TEN-ISO-001"]["status"], "PARTIAL")
        self.assertEqual(findings["SEC-AUTHZ-001"]["status"], "NOT_VERIFIABLE")

    def test_non_applicable_and_promotional_checks_do_not_fail_cli(self):
        report = audit("minimal-cli")
        findings = findings_by_id(report)
        self.assertEqual(report["summary"]["verdict"], "PASS")
        for check_id in ("SEC-RLS-001", "SEC-WEBHOOK-001", "TEN-ISO-001", "INF-DEPLOY-001", "PROD-VALUE-001"):
            self.assertEqual(findings[check_id]["status"], "NOT_APPLICABLE")
        self.assertTrue(findings["AI-PROMO-001"]["advisory"])
        self.assertNotIn("AI-PROMO-001", report["summary"]["failing_check_ids"])

    def test_every_finding_has_required_fields_and_status(self):
        report = audit("mixed-saas")
        required = {"check_id", "domain", "status", "severity", "confidence", "evidence_paths", "rationale", "remediation"}
        allowed = {"PASS", "MISSING", "PARTIAL", "NOT_APPLICABLE", "NOT_VERIFIABLE"}
        for item in report["findings"]:
            self.assertTrue(required.issubset(item))
            self.assertIn(item["status"], allowed)
            self.assertTrue(item["evidence_paths"])

    def test_monorepo_package_scripts_remain_package_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = root / "apps" / "api"
            web = root / "apps" / "web"
            (api / "src").mkdir(parents=True)
            (web / "tests").mkdir(parents=True)
            (api / "package.json").write_text(json.dumps({
                "name": "api",
                "scripts": {"start": "node src/index.js"},
                "dependencies": {"express": "5.1.0"},
            }))
            (api / "src" / "index.js").write_text("module.exports = {};\n")
            (web / "package.json").write_text(json.dumps({
                "name": "web",
                "scripts": {"test": "vitest run"},
                "devDependencies": {"vitest": "3.2.7"},
            }))
            (web / "tests" / "ui.test.js").write_text("export const covered = true;\n")

            completed = subprocess.run(
                [sys.executable, str(AUDIT), str(root), "--format", "json"],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(completed.stdout)
            evidence = findings_by_id(report)["DEV-TEST-001"]["evidence_paths"]
            self.assertIn("apps/web/package.json#scripts.test", evidence)
            self.assertNotIn("apps/api/package.json#scripts.test", evidence)
            self.assertEqual(
                {item["root"] for item in report["stack"]["package_contexts"]},
                {"apps/api", "apps/web"},
            )

    def test_aggregate_evidence_budget_reports_skipped_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text("a = 'more than ten bytes'\n")
            (root / "b.py").write_text("b = 'more than ten bytes'\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT),
                    str(root),
                    "--format",
                    "json",
                    "--max-total-text-bytes",
                    "10",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(completed.stdout)
            self.assertEqual(report["evidence_budget"]["max_total_text_bytes"], 10)
            self.assertEqual(report["evidence_budget"]["skipped_text_path_count"], 2)
            self.assertTrue(any("2 candidate file(s) were skipped" in item for item in report["limitations"]))

    def test_inventory_stops_at_file_and_candidate_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a.py", "b.py", "c.py", "d.bin"):
                (root / name).write_text("value = 1\n")

            file_limited = audit_path(root, "--max-inventory-files", "2")
            self.assertTrue(file_limited["evidence_budget"]["inventory_truncated"])
            self.assertEqual(file_limited["evidence_budget"]["inventoried_file_count"], 2)

            candidate_limited = audit_path(root, "--max-text-candidates", "2")
            self.assertTrue(candidate_limited["evidence_budget"]["inventory_truncated"])
            self.assertEqual(candidate_limited["evidence_budget"]["text_candidate_count"], 2)

    def test_secret_enforcement_reports_only_paths_and_honors_exclusions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = "-----BEGIN PRIVATE KEY-----"
            (root / "credential.py").write_text(f'MATERIAL = "{secret}"\n')
            report = audit_path(root)
            finding = findings_by_id(report)["SEC-SECRETS-001"]
            self.assertEqual(finding["status"], "MISSING")
            self.assertEqual(finding["evidence_paths"], ["credential.py:1"])
            self.assertNotIn(secret, json.dumps(finding))

            (root / "credential.py").unlink()
            (root / ".env.example").write_text(f'MATERIAL="{secret}"\n')
            fixture = root / "fixtures"
            fixture.mkdir()
            (fixture / "credential.py").write_text(f'MATERIAL = "{secret}"\n')
            excluded = findings_by_id(audit_path(root))["SEC-SECRETS-001"]
            self.assertEqual(excluded["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
