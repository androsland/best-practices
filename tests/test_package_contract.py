import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackageContractTests(unittest.TestCase):
    def test_manifests_share_name_and_version(self):
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(codex["name"], "project-practices")
        self.assertEqual(codex["name"], claude["name"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertEqual(codex["skills"], "./skills/")
        self.assertEqual(claude["skills"], "./skills/")

    def test_skills_have_no_scaffold_placeholders_and_references_resolve(self):
        for skill_name in ("project-practices-audit", "project-practices-curator"):
            skill = ROOT / "skills" / skill_name / "SKILL.md"
            text = skill.read_text()
            self.assertNotIn("[TODO:", text)
            self.assertIn(f"name: {skill_name}", text)
            for relative in __import__("re").findall(r"\]\((references/[^)]+\.md)\)", text):
                self.assertTrue((skill.parent / relative).exists(), relative)

    def test_fixture_lockfiles_are_resolved_not_placeholders(self):
        uv_lock = (ROOT / "fixtures/minimal-cli/uv.lock").read_text()
        self.assertIn('name = "pytest"', uv_lock)
        self.assertIn("sha256:", uv_lock)

        mixed_manifest = json.loads((ROOT / "fixtures/mixed-saas/package.json").read_text())
        mixed_lock = json.loads((ROOT / "fixtures/mixed-saas/package-lock.json").read_text())
        self.assertEqual(
            mixed_lock["packages"][""]["dependencies"],
            mixed_manifest["dependencies"],
        )
        self.assertGreater(len(mixed_lock["packages"]), 1)

    def test_security_migrations_encode_safe_rollout_and_rollback(self):
        migrations = ROOT / "fixtures/secure-saas/supabase/migrations"
        policies = (migrations / "202608280001_workspace_policies.sql").read_text()
        enable = (migrations / "202608280002_enable_projects_rls.sql").read_text()
        index = (migrations / "202608280003_processed_events_unique_index.sql").read_text()
        rollback = (
            ROOT / "fixtures/secure-saas/supabase/rollback/202608280003_security.sql"
        ).read_text()

        self.assertGreaterEqual(policies.lower().count("create policy"), 4)
        self.assertIn("enable row level security", enable.lower())
        self.assertIn("migrate:transaction=false", index)
        self.assertIn("having count(*) > 1", index.lower())
        self.assertIn("create unique index concurrently", index.lower())
        self.assertIn("drop index concurrently", rollback.lower())
        self.assertIn("disable row level security", rollback.lower())

    def test_negative_container_fixture_is_non_runnable_metadata(self):
        fixture = ROOT / "fixtures/mixed-saas"
        self.assertFalse((fixture / "Dockerfile").exists())
        metadata = json.loads((fixture / "container-negative-fixture.json").read_text())
        self.assertEqual(metadata["artifact_type"], "non-runnable-negative-evidence")


if __name__ == "__main__":
    unittest.main()
