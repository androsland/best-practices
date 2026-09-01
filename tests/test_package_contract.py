import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fixture_artifact(root: Path, relative: str) -> Path:
    return root / f"{relative}.fixture"


class PackageContractTests(unittest.TestCase):
    def test_manifests_share_name_and_version(self):
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(codex["name"], "best-practices")
        self.assertEqual(codex["name"], claude["name"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertEqual(codex["skills"], "./skills/")
        self.assertEqual(claude["skills"], "./skills/")

    def test_skills_have_no_scaffold_placeholders_and_references_resolve(self):
        for skill_name in (
            "best-practices-audit",
            "best-practices-catalog",
            "best-practices-curator",
            "best-practices-ingest",
        ):
            skill = ROOT / "skills" / skill_name / "SKILL.md"
            text = skill.read_text()
            self.assertNotIn("[TODO:", text)
            self.assertIn(f"name: {skill_name}", text)
            for relative in __import__("re").findall(r"\]\((references/[^)]+\.md)\)", text):
                self.assertTrue((skill.parent / relative).exists(), relative)

    def test_manifest_describes_the_multi_agent_knowledge_product(self):
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(codex["version"], "0.2.0")
        self.assertIn("multi-agent", codex["description"])
        self.assertIn("Contextual multi-agent reviews", codex["interface"]["capabilities"])
        self.assertLessEqual(len(codex["interface"]["defaultPrompt"]), 3)

    def test_fixture_lockfiles_are_resolved_not_placeholders(self):
        uv_lock = (ROOT / "fixtures/minimal-cli/uv.lock").read_text()
        self.assertIn('name = "pytest"', uv_lock)
        self.assertIn("sha256:", uv_lock)

        mixed_fixture = ROOT / "fixtures/mixed-saas"
        mixed_manifest = json.loads(
            fixture_artifact(mixed_fixture, "package.json").read_text()
        )
        mixed_lock = json.loads(
            fixture_artifact(mixed_fixture, "package-lock.json").read_text()
        )
        self.assertEqual(
            mixed_lock["packages"][""]["dependencies"],
            mixed_manifest["dependencies"],
        )
        self.assertGreater(len(mixed_lock["packages"]), 1)

        secure_fixture = ROOT / "fixtures/secure-saas"
        secure_lock = json.loads(
            fixture_artifact(secure_fixture, "package-lock.json").read_text()
        )
        lifecycle_scripts = {
            f"{path}@{package.get('version')}"
            for path, package in secure_lock["packages"].items()
            if package.get("hasInstallScript")
        }
        self.assertEqual(
            lifecycle_scripts,
            {"node_modules/esbuild@0.28.2", "node_modules/fsevents@2.3.3"},
        )

        supply_chain_review = (
            fixture_artifact(secure_fixture, "docs/supply-chain-review.md")
        ).read_text()
        self.assertIn("@img/sharp-libvips-*", supply_chain_review)
        self.assertIn("LGPL-3.0-or-later", supply_chain_review)
        self.assertIn("never installs or redistributes", supply_chain_review)

    def test_security_migrations_encode_safe_rollout_and_rollback(self):
        migrations = ROOT / "fixtures/secure-saas/supabase/migrations"
        workspace_index = (
            fixture_artifact(migrations, "202608280000_projects_workspace_index.sql")
        ).read_text()
        policies = fixture_artifact(
            migrations, "202608280001_workspace_policies.sql"
        ).read_text()
        enable_path = (
            ROOT
            / "fixtures/secure-saas/supabase/release-phases/phase-2/202608280002_enable_projects_rls.sql.fixture"
        )
        enable = enable_path.read_text()
        index = fixture_artifact(
            migrations, "202608280003_processed_events_unique_index.sql"
        ).read_text()
        rollback = (
            ROOT / "fixtures/secure-saas/supabase/rollback/202608280003_security.sql.fixture"
        ).read_text()

        self.assertFalse((migrations / enable_path.name.removesuffix(".fixture")).exists())
        self.assertIn("create index concurrently projects_workspace_id_idx", workspace_index.lower())
        self.assertGreaterEqual(policies.lower().count("create policy"), 4)
        self.assertIn("enable row level security", enable.lower())
        self.assertIn("lock_timeout", enable.lower())
        self.assertIn("migrate:transaction=false", index)
        self.assertIn("having count(*) > 1", index.lower())
        self.assertIn("create unique index concurrently", index.lower())
        self.assertNotIn("if not exists processed_events_event_id_key", index.lower())
        self.assertIn("drop index concurrently", rollback.lower())
        self.assertIn("disable row level security", rollback.lower())

    def test_negative_container_fixture_is_non_runnable_metadata(self):
        fixture = ROOT / "fixtures/mixed-saas"
        self.assertFalse((fixture / "Dockerfile").exists())
        metadata = json.loads((fixture / "container-negative-fixture.json").read_text())
        self.assertEqual(metadata["artifact_type"], "non-runnable-negative-evidence")

    def test_negative_api_fixture_has_no_runtime_entrypoint(self):
        fixture = ROOT / "fixtures/mixed-saas"
        manifest = json.loads(fixture_artifact(fixture, "package.json").read_text())
        server = fixture_artifact(fixture, "src/server.js").read_text()
        self.assertTrue(manifest["private"])
        self.assertNotIn("start", manifest.get("scripts", {}))
        self.assertNotIn(".listen(", server)
        self.assertNotIn("module.exports", server)
        self.assertFalse((fixture / "package.json").exists())
        self.assertFalse((fixture / "src/server.js").exists())

    def test_saas_fixtures_are_marked_inert_virtual_projects(self):
        for name in ("mixed-saas", "secure-saas"):
            fixture = ROOT / "fixtures" / name
            marker = json.loads(
                (fixture / ".best-practices-fixture.json").read_text()
            )
            self.assertEqual(
                marker,
                {
                    "schema_version": 1,
                    "artifact_type": "static-analyzer-virtual-project",
                },
            )
            self.assertTrue(list(fixture.rglob("*.fixture")))

    def test_root_ci_runs_the_single_validation_entrypoint(self):
        validation_script = (ROOT / "scripts/validate.sh").read_text()
        self.assertNotIn("npm --prefix fixtures", validation_script)
        workflow = (ROOT / ".github/workflows/validate.yml").read_text()
        self.assertIn("./scripts/validate.sh", workflow)
        self.assertIn("actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955", workflow)
        fixture_workflow = (
            ROOT / "fixtures/secure-saas/.github/workflows/validate.yml.fixture"
        ).read_text()
        self.assertIn(
            "actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955",
            fixture_workflow,
        )


if __name__ == "__main__":
    unittest.main()
