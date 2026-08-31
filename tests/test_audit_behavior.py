import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "skills/project-practices-audit/scripts/audit_evidence.py"
EXPECTED_CHECK_IDS = {
    "DEV-SCOPE-001", "DEV-TEST-001", "DEV-CI-001", "DEV-DEPS-001", "DEV-STATE-001",
    "SEC-AUTHZ-001", "SEC-SESS-001", "SEC-AUTHN-001", "SEC-RLS-001", "SEC-WEBHOOK-001",
    "SEC-API-001", "SEC-EDGE-001", "SEC-MOBILE-001", "SEC-SECRETS-001",
    "REL-RPO-001", "REL-BACKUP-001", "REL-RESTORE-001", "REL-MIGRATE-001", "REL-OBS-001",
    "TEN-ISO-001", "TEN-EXT-001", "TEN-NOISY-001", "TEN-MIGRATE-001",
    "INF-DEPLOY-001", "INF-SECRET-001", "INF-NET-001", "INF-PATCH-001", "INF-OBS-001", "INF-TLS-001",
    "PROD-VALUE-001", "PROD-FLOW-001", "PROD-DISCLOSE-001", "PROD-REENGAGE-001", "PROD-MEASURE-001",
    "AI-DATA-001", "AI-KEY-001", "AI-OUTPUT-001", "AI-EVAL-001", "AI-SUPPLY-001", "AI-PROMO-001",
}


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
        emitted = [item["check_id"] for item in report["findings"]]
        self.assertEqual(len(emitted), len(set(emitted)))
        self.assertEqual(set(emitted), EXPECTED_CHECK_IDS)

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

    def test_fixture_suffix_is_virtualized_only_for_marked_fixture_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py.fixture").write_text("print('analyzer input')\n")

            ordinary = audit_path(root)
            self.assertNotIn("python", ordinary["stack"]["languages"])
            self.assertEqual(
                findings_by_id(ordinary)["DEV-TEST-001"]["status"],
                "NOT_APPLICABLE",
            )

            (root / ".project-practices-fixture.json").write_text(json.dumps({
                "schema_version": 1,
                "artifact_type": "static-analyzer-virtual-project",
            }))
            fixture = audit_path(root)
            self.assertIn("python", fixture["stack"]["languages"])
            self.assertEqual(
                findings_by_id(fixture)["DEV-TEST-001"]["status"],
                "MISSING",
            )

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

    def test_secret_detection_requires_literal_credential_material(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "credentials.ts"
            source.write_text(
                "const password = crypto.randomUUID()\n"
                "const token = session.accessToken\n"
                "const apiKey = process.env.API_KEY\n"
            )
            computed = findings_by_id(audit_path(root))["SEC-SECRETS-001"]
            self.assertEqual(computed["status"], "PASS")

            source.write_text('const apiKey = "sk_live_1234567890abcdef"\n')
            literal = findings_by_id(audit_path(root))["SEC-SECRETS-001"]
            self.assertEqual(literal["status"], "MISSING")
            self.assertEqual(literal["evidence_paths"], ["credentials.ts:1"])
            self.assertNotIn("sk_live_1234567890abcdef", json.dumps(literal))

            source.unlink()
            (root / "config.json").write_text(json.dumps({"accessToken": "actual_1234567890abcdef"}))
            json_literal = findings_by_id(audit_path(root))["SEC-SECRETS-001"]
            self.assertEqual(json_literal["status"], "MISSING")
            self.assertEqual(json_literal["evidence_paths"], ["config.json:1"])

    def test_recovery_checks_require_measurable_targets_and_drill_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            specs = root / "specs"
            migrations = root / "migrations"
            docs.mkdir()
            specs.mkdir()
            migrations.mkdir()
            (migrations / "001.sql").write_text("create table records (id bigint primary key);\n")
            recovery = docs / "recovery.md"
            recovery.write_text(
                "RPO/RTO and restore-test cadence still need to be defined.\n"
                "Ask the operations owner about the recovery exercise.\n"
            )
            (specs / "billing.md").write_text(
                "Restore procedure: copy the saved promotion snapshot back into the account at expiry.\n"
            )
            unresolved = findings_by_id(audit_path(root))
            self.assertEqual(unresolved["REL-RPO-001"]["status"], "NOT_VERIFIABLE")
            self.assertEqual(unresolved["REL-RESTORE-001"]["status"], "NOT_VERIFIABLE")

            recovery.write_text(
                "Critical records have a 15-minute RPO and an RTO of 2 hours.\n"
                "The restore runbook restores the latest backup into an isolated environment and verifies critical reads.\n"
                "The most recent recovery exercise completed within the target.\n"
            )
            measured = findings_by_id(audit_path(root))
            self.assertEqual(measured["REL-RPO-001"]["status"], "PASS")
            self.assertEqual(measured["REL-RESTORE-001"]["status"], "PASS")

    def test_agent_supply_chain_cannot_be_documented_past_a_floating_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                "Record canonical provenance, exact version or commit, license, permissions, and network destinations.\n"
            )
            mcp = root / ".mcp.json"
            mcp.write_text(json.dumps({
                "mcpServers": {
                    "database": {
                        "command": "npx",
                        "args": ["-y", "@vendor/database-mcp@latest"],
                    },
                },
            }))
            floating = findings_by_id(audit_path(root))["AI-SUPPLY-001"]
            self.assertEqual(floating["status"], "PARTIAL")
            self.assertEqual(floating["confidence"], "HIGH")
            self.assertIn(".mcp.json", floating["evidence_paths"][0])

            mcp.write_text(json.dumps({
                "mcpServers": {
                    "database": {
                        "command": "pnpm",
                        "args": ["dlx", "database-mcp"],
                    },
                },
            }))
            unversioned_dlx = findings_by_id(audit_path(root))["AI-SUPPLY-001"]
            self.assertEqual(unversioned_dlx["status"], "PARTIAL")

            mcp.write_text(json.dumps({
                "mcpServers": {
                    "database": {
                        "command": "npx",
                        "args": ["-y", "@vendor/database-mcp@1.2.3"],
                    },
                },
            }))
            pinned = findings_by_id(audit_path(root))["AI-SUPPLY-001"]
            self.assertEqual(pinned["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
