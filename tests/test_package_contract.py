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


if __name__ == "__main__":
    unittest.main()
