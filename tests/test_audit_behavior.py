import hashlib
import json
import subprocess
import sys
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
        self.assertEqual(findings["DEV-DEPS-001"]["status"], "MISSING")
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


if __name__ == "__main__":
    unittest.main()
