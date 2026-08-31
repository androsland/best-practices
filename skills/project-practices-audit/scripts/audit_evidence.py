#!/usr/bin/env python3
"""Collect conservative, read-only repository evidence for project-practices-audit."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".next", ".nuxt", ".output", ".turbo",
    ".venv", "venv", "node_modules", "vendor", "dist", "build", "coverage",
    "target", "Pods", "DerivedData", "__pycache__",
}
TEXT_SUFFIXES = {
    ".c", ".cc", ".conf", ".cpp", ".cs", ".css", ".env", ".example",
    ".go", ".graphql", ".h", ".html", ".java", ".js", ".json", ".jsx",
    ".kt", ".kts", ".md", ".mjs", ".php", ".properties", ".py", ".rb",
    ".rs", ".sh", ".sql", ".swift", ".tf", ".toml", ".ts", ".tsx",
    ".txt", ".xml", ".yaml", ".yml",
}
MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "poetry.lock",
    "Pipfile", "Pipfile.lock", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "Gemfile", "Gemfile.lock",
    "composer.json", "composer.lock", "Package.swift", "Podfile", "Podfile.lock",
}
LOCK_NAMES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "bun.lock", "bun.lockb", "poetry.lock", "Pipfile.lock", "uv.lock", "go.sum",
    "Cargo.lock", "Gemfile.lock", "composer.lock", "Podfile.lock",
}
CODE_SUFFIXES = {".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".kt", ".php", ".py", ".rb", ".rs", ".swift", ".ts", ".tsx"}
TEST_RE = re.compile(r"(^|/)(tests?|spec|__tests__)(/|$)|(^|/)[^/]+\.(test|spec)\.[^.]+$", re.I)
FIXTURE_MARKER = ".project-practices-fixture.json"
FIXTURE_ARTIFACT_TYPE = "static-analyzer-virtual-project"


@dataclass(frozen=True)
class TextFile:
    path: Path
    rel: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class PackageContext:
    path: str
    root: str
    dependencies: frozenset[str]
    scripts: dict[str, str]


class Repository:
    def __init__(self, root: Path, max_file_bytes: int = 1_000_000,
                 max_total_text_bytes: int = 25_000_000,
                 max_inventory_files: int = 100_000,
                 max_text_candidates: int = 50_000,
                 max_skipped_path_samples: int = 100) -> None:
        self.root = root.resolve()
        self.max_file_bytes = max_file_bytes
        self.max_total_text_bytes = max_total_text_bytes
        self.max_inventory_files = max_inventory_files
        self.max_text_candidates = max_text_candidates
        self.max_skipped_path_samples = max_skipped_path_samples
        self.virtual_fixture = self._is_virtual_fixture()
        self.paths: list[Path] = []
        self.text_files: list[TextFile] = []
        self.skipped_text_paths: list[str] = []
        self.skipped_text_path_count = 0
        self.inventoried_file_count = 0
        self.text_candidate_count = 0
        self.inventory_truncated = False
        self.scanned_text_bytes = 0
        self._inventory()

    def _is_virtual_fixture(self) -> bool:
        marker = self.root / FIXTURE_MARKER
        if marker.is_symlink() or not marker.is_file():
            return False
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return (
            data.get("schema_version") == 1
            and data.get("artifact_type") == FIXTURE_ARTIFACT_TYPE
        )

    def _logical_rel(self, path: Path) -> str:
        rel = path.relative_to(self.root).as_posix()
        if self.virtual_fixture and rel.endswith(".fixture"):
            return rel.removesuffix(".fixture")
        return rel

    def _record_skipped_text(self, rel: str) -> None:
        self.skipped_text_path_count += 1
        if len(self.skipped_text_paths) < self.max_skipped_path_samples:
            self.skipped_text_paths.append(rel)

    def _inventory(self) -> None:
        for current, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS and not Path(current, d).is_symlink())
            for name in sorted(names):
                path = Path(current, name)
                if path.is_symlink() or not path.is_file():
                    continue
                if self.inventoried_file_count >= self.max_inventory_files:
                    self.inventory_truncated = True
                    return
                self.inventoried_file_count += 1
                self.paths.append(path)
                if not self._is_text_candidate(path):
                    continue
                if self.text_candidate_count >= self.max_text_candidates:
                    self.inventory_truncated = True
                    return
                self.text_candidate_count += 1
                try:
                    size = path.stat().st_size
                    rel = self._logical_rel(path)
                    if size > self.max_file_bytes:
                        self._record_skipped_text(rel)
                        continue
                    if self.scanned_text_bytes + size > self.max_total_text_bytes:
                        self._record_skipped_text(rel)
                        continue
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                self.scanned_text_bytes += size
                self.text_files.append(TextFile(path, rel, tuple(text.splitlines())))

    def _is_text_candidate(self, path: Path) -> bool:
        logical = Path(self._logical_rel(path))
        return logical.name in MANIFEST_NAMES or logical.name.startswith("Dockerfile") or logical.suffix.lower() in TEXT_SUFFIXES

    def relatives(self) -> list[str]:
        return [self._logical_rel(path) for path in self.paths]

    def named(self, names: set[str]) -> list[str]:
        return sorted(
            self._logical_rel(path)
            for path in self.paths
            if Path(self._logical_rel(path)).name in names
        )

    def paths_matching(self, pattern: re.Pattern[str]) -> list[str]:
        return sorted(rel for rel in self.relatives() if pattern.search(rel))

    def grep(self, patterns: Sequence[str], *, paths: Iterable[TextFile] | None = None, limit: int = 12) -> list[str]:
        compiled = [re.compile(pattern, re.I) for pattern in patterns]
        matches: list[str] = []
        for item in paths or self.text_files:
            for line_no, line in enumerate(item.lines, 1):
                if any(pattern.search(line) for pattern in compiled):
                    matches.append(f"{item.rel}:{line_no}")
                    break
            if len(matches) >= limit:
                break
        return sorted(set(matches))

    def contains(self, patterns: Sequence[str]) -> bool:
        return bool(self.grep(patterns, limit=1))

    def nearest_context(self) -> list[str]:
        manifests = sorted(
            self._logical_rel(path)
            for path in self.paths
            if Path(self._logical_rel(path)).name
            in MANIFEST_NAMES | {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}
        )
        return manifests[:3] or ["."]


def package_contexts(repo: Repository) -> list[PackageContext]:
    contexts: list[PackageContext] = []
    for item in repo.text_files:
        if Path(item.rel).name != "package.json":
            continue
        try:
            data = json.loads(item.text)
        except json.JSONDecodeError:
            continue
        dependencies: set[str] = set()
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            values = data.get(key, {})
            if isinstance(values, dict):
                dependencies.update(values)
        scripts = data.get("scripts", {})
        contexts.append(PackageContext(
            path=item.rel,
            root=Path(item.rel).parent.as_posix(),
            dependencies=frozenset(dependencies),
            scripts=scripts if isinstance(scripts, dict) else {},
        ))
    return sorted(contexts, key=lambda context: context.path)


def detect_stack(repo: Repository) -> dict:
    rels = repo.relatives()
    suffixes = {Path(rel).suffix.lower() for rel in rels}
    names = {Path(rel).name for rel in rels}
    packages = package_contexts(repo)
    package_paths = [package.path for package in packages]
    deps = set().union(*(package.dependencies for package in packages)) if packages else set()
    languages: list[str] = []
    for language, candidates in {
        "javascript-typescript": {".js", ".jsx", ".mjs", ".ts", ".tsx"},
        "python": {".py"}, "go": {".go"}, "rust": {".rs"},
        "java-kotlin": {".java", ".kt", ".kts"}, "dotnet": {".cs"},
        "ruby": {".rb"}, "php": {".php"}, "swift": {".swift"},
    }.items():
        if suffixes & candidates:
            languages.append(language)

    frameworks = sorted({
        label for label, packages in {
            "nextjs": {"next"}, "react": {"react"}, "express": {"express"},
            "fastify": {"fastify"}, "nestjs": {"@nestjs/core"}, "supabase": {"@supabase/supabase-js"},
            "stripe": {"stripe"}, "openai": {"openai"}, "anthropic": {"@anthropic-ai/sdk"},
        }.items() if deps & packages
    })
    python_blob = "\n".join(i.text for i in repo.text_files if Path(i.rel).name in {"pyproject.toml", "requirements.txt", "Pipfile"})
    for label, pattern in {"django": r"\bdjango\b", "fastapi": r"\bfastapi\b", "flask": r"\bflask\b", "sqlalchemy": r"\bsqlalchemy\b", "pytest": r"\bpytest\b", "openai": r"\bopenai\b", "anthropic": r"\banthropic\b"}.items():
        if re.search(pattern, python_blob, re.I):
            frameworks.append(label)
    frameworks = sorted(set(frameworks))

    code = bool(suffixes & CODE_SUFFIXES)
    infrastructure = any(re.search(r"(^|/)(Dockerfile[^/]*|docker-compose\.ya?ml|terraform/|infra/|k8s/|\.github/workflows/)", rel, re.I) for rel in rels) or ".tf" in suffixes
    network_service = bool(set(frameworks) & {"nextjs", "express", "fastify", "nestjs", "django", "fastapi", "flask"}) or repo.contains([r"\b(app\.(get|post|put|patch|delete)|router\.(get|post|put|patch|delete)|@app\.(get|post|put|patch|delete))\b"])
    auth = repo.contains([r"\b(login|sign[-_ ]?in|password[-_ ]?reset|auth(n|entication|orization)?)\b"])
    supabase = "supabase" in frameworks or any(rel.startswith("supabase/") for rel in rels)
    webhook = repo.contains([r"\bwebhook\b", r"stripe-signature", r"constructEvent"])
    durable_data = bool(set(frameworks) & {"supabase", "sqlalchemy", "django"}) or repo.contains([r"\b(postgres|postgresql|mysql|sqlite|mongodb|prisma|drizzle|database_url)\b"]) or any("migration" in rel.lower() for rel in rels)
    tenant_evidence = repo.grep([r"\b(tenant_id|tenantId|workspace_id|workspaceId|organization_id|organizationId)\b"], limit=8)
    multitenant = bool(tenant_evidence)
    onboarding_path = any(re.search(r"(^|/)(onboarding|signup|activation)(/|\.|$)", rel, re.I) for rel in rels)
    end_user_product = bool(set(frameworks) & {"nextjs", "react", "django"}) and (onboarding_path or repo.contains([r"\b(sign[-_ ]?up|onboarding|welcome|activation)[_ -]?"]))
    ai = bool(set(frameworks) & {"openai", "anthropic"}) or repo.contains([r"\b(openai|anthropic|llm|language model|model provider)\b"])
    agent_extensions = any(re.search(r"(^|/)(\.mcp\.json|SKILL\.md|CLAUDE\.md|AGENTS\.md|\.claude-plugin/plugin\.json|\.codex-plugin/plugin\.json)$", rel) for rel in rels)
    mobile = any(name in names for name in {"AndroidManifest.xml", "Podfile", "capacitor.config.ts", "capacitor.config.json"}) or any(rel.endswith(".xcodeproj/project.pbxproj") for rel in rels)
    return {
        "languages": sorted(languages),
        "frameworks": frameworks,
        "manifests": sorted(set(package_paths + repo.named(MANIFEST_NAMES))),
        "package_contexts": [
            {"path": package.path, "root": package.root, "dependencies": sorted(package.dependencies)}
            for package in packages
        ],
        "surfaces": {
            "code": code, "network_service": network_service, "authentication": auth,
            "supabase": supabase, "webhooks": webhook, "durable_data": durable_data,
            "multitenant": multitenant, "infrastructure_deployment": infrastructure,
            "end_user_product": end_user_product, "ai_usage": ai,
            "agent_extensions": agent_extensions, "mobile": mobile,
        },
        "surface_evidence": {"multitenant": tenant_evidence},
    }


def finding(check_id: str, domain: str, status: str, severity: str, confidence: str,
            evidence: Sequence[str], rationale: str, remediation: str | None,
            *, advisory: bool = False) -> dict:
    return {
        "check_id": check_id, "domain": domain, "status": status,
        "severity": "INFO" if status == "NOT_APPLICABLE" else severity,
        "confidence": confidence, "evidence_paths": list(evidence) or ["."],
        "rationale": rationale, "remediation": remediation,
        "advisory": advisory,
    }


def collect_development_findings(repo: Repository, stack: dict) -> list[dict]:
    surfaces, context = stack["surfaces"], repo.nearest_context()
    results: list[dict] = []
    test_paths = repo.paths_matching(TEST_RE)
    test_commands = [
        f"{package.path}#scripts.{name}"
        for package in package_contexts(repo)
        for name in ("test", "test:unit", "check")
        if name in package.scripts
    ]
    python_test_cmd = repo.grep([r"\b(pytest|unittest)\b"], paths=(i for i in repo.text_files if Path(i.rel).name in {"pyproject.toml", "tox.ini", "Makefile"}))
    if not surfaces["code"]:
        results.append(finding("DEV-TEST-001", "coding-ai", "NOT_APPLICABLE", "HIGH", "HIGH", context, "No executable source-code surface was detected.", None))
    elif test_paths and (test_commands or python_test_cmd):
        results.append(finding("DEV-TEST-001", "coding-ai", "PASS", "HIGH", "HIGH", (test_paths[:6] + test_commands + python_test_cmd)[:10], "Automated tests and a package-scoped runnable test command were found.", None))
    elif test_paths or test_commands or python_test_cmd:
        results.append(finding("DEV-TEST-001", "coding-ai", "PARTIAL", "HIGH", "HIGH", (test_paths[:6] + test_commands + python_test_cmd) or context, "Only tests or a runnable test command were found, not both.", "Add representative automated tests and expose a repeatable test command used by contributors or CI."))
    else:
        results.append(finding("DEV-TEST-001", "coding-ai", "MISSING", "HIGH", "HIGH", context + ["(searched test/spec directories and package-scoped manifest scripts)"], "The nontrivial codebase has no discovered automated tests or runnable test command.", "Add risk-focused tests and a repeatable command that runs them."))

    ci_paths = [r for r in repo.relatives() if re.search(r"(^|/)\.github/workflows/.*\.ya?ml$|(^|/)(\.gitlab-ci\.yml|azure-pipelines\.ya?ml|Jenkinsfile)$", r)]
    ci_validation = repo.grep([r"\b(npm|pnpm|yarn|bun)\s+(run\s+)?(test|lint|check|build|typecheck)\b", r"\b(pytest|go test|cargo test|mvn test|gradle test|dotnet test)\b"], paths=(i for i in repo.text_files if i.rel in ci_paths))
    if not surfaces["code"]:
        results.append(finding("DEV-CI-001", "coding-ai", "NOT_APPLICABLE", "MEDIUM", "HIGH", context, "No executable source-code surface was detected.", None))
    elif ci_paths and ci_validation:
        results.append(finding("DEV-CI-001", "coding-ai", "PASS", "MEDIUM", "HIGH", ci_validation, "A checked-in CI workflow invokes project validation.", None))
    elif ci_paths:
        results.append(finding("DEV-CI-001", "coding-ai", "PARTIAL", "MEDIUM", "HIGH", ci_paths[:8], "CI configuration exists but no recognizable validation invocation was found.", "Run the project's relevant validation commands on pull requests."))
    else:
        results.append(finding("DEV-CI-001", "coding-ai", "NOT_VERIFIABLE", "MEDIUM", "MEDIUM", context + ["(searched common CI configuration paths)"], "No checked-in CI was found; validation may be configured outside the repository.", "Document the external CI or add a checked-in workflow that runs applicable validation."))

    dependency_manifests = [p for p in stack["manifests"] if Path(p).name not in LOCK_NAMES]
    locks = repo.named(LOCK_NAMES)
    if not dependency_manifests:
        results.append(finding("DEV-DEPS-001", "coding-ai", "NOT_APPLICABLE", "MEDIUM", "HIGH", context, "No dependency manifest was detected.", None))
    elif locks:
        results.append(finding("DEV-DEPS-001", "coding-ai", "PASS", "MEDIUM", "HIGH", locks, "A reproducibility lock/checksum file accompanies dependency manifests.", None))
    else:
        results.append(finding("DEV-DEPS-001", "coding-ai", "MISSING", "MEDIUM", "HIGH", dependency_manifests + ["(searched ecosystem lockfiles)"], "Dependency manifests exist without a discovered lock/checksum file.", "Generate and commit the ecosystem's supported lock/checksum file."))
    return results


def collect_security_findings(repo: Repository, stack: dict) -> list[dict]:
    surfaces, context = stack["surfaces"], repo.nearest_context()
    results: list[dict] = []
    secret_evidence: list[str] = []
    private_key_re = re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
    assignment_re = re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?(?!\$\{|process\.env|os\.environ|env\.|<|example|changeme|test|dummy)[A-Za-z0-9_./+=-]{16,}")
    for item in repo.text_files:
        if Path(item.rel).name.endswith((".example", ".sample")) or "/fixtures/" in f"/{item.rel}/":
            continue
        for line_no, line in enumerate(item.lines, 1):
            if private_key_re.search(line) or assignment_re.search(line):
                secret_evidence.append(f"{item.rel}:{line_no}")
                break
    if secret_evidence:
        results.append(finding("SEC-SECRETS-001", "application-security", "MISSING", "CRITICAL", "MEDIUM", secret_evidence[:10], "Potential committed credential material was detected; values were intentionally not reported.", "Validate each match, revoke and rotate real credentials, remove them from current files and history, and use secret injection."))
    else:
        results.append(finding("SEC-SECRETS-001", "application-security", "PASS", "CRITICAL", "MEDIUM", context + ["(bounded text scan; secret values not emitted)"], "No obvious committed private-key marker or high-confidence credential assignment was detected by the bounded scan.", None))
    if not (surfaces["network_service"] and surfaces["authentication"]):
        results.append(finding("SEC-AUTHZ-001", "application-security", "NOT_APPLICABLE", "CRITICAL", "MEDIUM", context, "No authenticated network-service surface was confidently detected.", None))
    else:
        evidence = repo.grep([r"\b(authoriz(e|ation)|permission|policy|canAccess|requireRole|owner_id|user_id)\b"])
        results.append(finding("SEC-AUTHZ-001", "application-security", "NOT_VERIFIABLE", "CRITICAL", "MEDIUM", evidence or context, "Authorization correctness and object scope require route/data-flow inspection; keyword evidence cannot prove coverage.", "Inspect every protected operation and add negative unauthorized and cross-user tests."))
    if not surfaces["supabase"]:
        results.append(finding("SEC-RLS-001", "application-security", "NOT_APPLICABLE", "CRITICAL", "HIGH", context, "No Supabase/PostgREST surface was detected.", None))
    else:
        rls, policies = repo.grep([r"enable\s+row\s+level\s+security"]), repo.grep([r"create\s+policy"])
        if rls and policies:
            results.append(finding("SEC-RLS-001", "application-security", "PASS", "CRITICAL", "HIGH", rls + policies, "Migrations enable RLS and define policies; role/grant behavior still warrants targeted tests.", None))
        elif rls or policies:
            results.append(finding("SEC-RLS-001", "application-security", "PARTIAL", "CRITICAL", "HIGH", rls + policies, "Only part of the expected RLS enablement/policy evidence was found.", "Enable RLS for every exposed table, define least-privilege policies/grants, and add anon/authenticated role tests."))
        else:
            results.append(finding("SEC-RLS-001", "application-security", "MISSING", "CRITICAL", "HIGH", context + ["(searched SQL/migrations for RLS and policies)"], "Supabase was detected but no checked-in RLS enablement or policy evidence was found.", "Add reviewed RLS/grant migrations and negative role/row access tests for exposed schemas."))
    if not surfaces["webhooks"]:
        results.append(finding("SEC-WEBHOOK-001", "application-security", "NOT_APPLICABLE", "CRITICAL", "HIGH", context, "No webhook handler surface was detected.", None))
    else:
        signature = repo.grep([r"stripe-signature", r"constructEvent", r"verify(Webhook|Signature|Header)", r"timingSafeEqual"])
        idempotency = repo.grep([r"\b(event_id|eventId|idempot|processed_events|on conflict|unique)\b"])
        if signature and idempotency:
            results.append(finding("SEC-WEBHOOK-001", "application-security", "PASS", "CRITICAL", "MEDIUM", signature + idempotency, "Signature-verification and duplicate-delivery boundary signals were found; inspect ordering before side effects.", None))
        elif signature or idempotency:
            results.append(finding("SEC-WEBHOOK-001", "application-security", "PARTIAL", "CRITICAL", "MEDIUM", signature + idempotency, "Only signature verification or retry/idempotency evidence was found.", "Verify the provider signature over the required raw body before effects and persist an idempotency boundary for retries."))
        else:
            results.append(finding("SEC-WEBHOOK-001", "application-security", "MISSING", "CRITICAL", "MEDIUM", context + ["(searched webhook implementation for signature and idempotency signals)"], "A webhook surface exists without recognizable authenticity or duplicate-delivery controls.", "Use the provider's official signature verifier before side effects and make repeated event delivery safe."))
    return results


def collect_reliability_findings(repo: Repository, stack: dict) -> list[dict]:
    surfaces, context = stack["surfaces"], repo.nearest_context()
    results: list[dict] = []
    if not surfaces["durable_data"]:
        results.extend([
            finding("REL-RPO-001", "data-reliability", "NOT_APPLICABLE", "HIGH", "HIGH", context, "No durable data surface was detected.", None),
            finding("REL-RESTORE-001", "data-reliability", "NOT_APPLICABLE", "HIGH", "HIGH", context, "No durable data surface was detected.", None),
        ])
    else:
        rpo_rto = repo.grep([r"\bRPO\b", r"\bRTO\b"])
        restore = repo.grep([r"\brestore\b", r"recovery drill", r"restore test"])
        results.append(finding("REL-RPO-001", "data-reliability", "PASS" if rpo_rto else "NOT_VERIFIABLE", "HIGH", "MEDIUM", rpo_rto or context + ["(searched for RPO/RTO)"], "Repository recovery objectives were found." if rpo_rto else "Recovery objectives may be maintained outside the repository.", None if rpo_rto else "Document owned RPO/RTO targets and link backup/retention design to them."))
        if restore:
            drill = repo.grep([r"restore (test|drill)", r"measured.*RTO", r"recovery exercise"])
            results.append(finding("REL-RESTORE-001", "data-reliability", "PASS" if drill else "PARTIAL", "HIGH", "MEDIUM", restore + drill, "Restore guidance exists" + (" with drill evidence." if drill else " but no clear timed drill evidence."), None if drill else "Run an isolated restore drill, verify critical paths, measure against RTO, and record the result."))
        else:
            results.append(finding("REL-RESTORE-001", "data-reliability", "NOT_VERIFIABLE", "HIGH", "MEDIUM", context + ["(searched for restore/runbook/drill evidence)"], "No repository restore evidence was found; recovery records may be external.", "Link or add the restore runbook and recent drill evidence without exposing sensitive operational values."))
    test_paths = repo.paths_matching(TEST_RE)
    if not surfaces["multitenant"]:
        results.append(finding("TEN-ISO-001", "multitenancy", "NOT_APPLICABLE", "CRITICAL", "HIGH", context, "No direct tenant/workspace/organization data-model signal was detected.", None))
    else:
        filters = repo.grep([r"\b(tenant_id|tenantId|workspace_id|workspaceId|organization_id|organizationId)\b"])
        tests = [path for path in test_paths if re.search(r"tenant|workspace|organization", path, re.I)]
        results.append(finding("TEN-ISO-001", "multitenancy", "PASS" if filters and tests else "PARTIAL", "CRITICAL", "MEDIUM", (filters[:5] + tests[:5]) or stack["surface_evidence"]["multitenant"], "Tenant scoping and tenant-focused test paths were found; inspect negative cross-tenant assertions." if filters and tests else "Tenant identifiers were found without tenant-focused test evidence.", None if filters and tests else "Centralize tenant scoping and add negative cross-tenant read/write tests at the data boundary."))
    deploy_paths = [r for r in repo.relatives() if re.search(r"(^|/)(Dockerfile|docker-compose|terraform/|infra/|k8s/|\.github/workflows/)", r, re.I) or r.endswith(".tf")]
    if not surfaces["infrastructure_deployment"]:
        results.append(finding("INF-DEPLOY-001", "infrastructure-deployment", "NOT_APPLICABLE", "HIGH", "HIGH", context, "No deployment or infrastructure surface was detected.", None))
    else:
        rollback = repo.grep([r"\brollback\b", r"roll back", r"previous (release|revision|image)"])
        results.append(finding("INF-DEPLOY-001", "infrastructure-deployment", "PASS" if deploy_paths and rollback else "PARTIAL", "HIGH", "MEDIUM", (deploy_paths[:5] + rollback) if deploy_paths and rollback else deploy_paths[:8] or context, "Versioned deployment artifacts and rollback guidance were found." if deploy_paths and rollback else "Deployment evidence exists without a recognizable rollback/recovery path.", None if deploy_paths and rollback else "Document and test how to return to a known-good release, including data migration constraints."))
    return results


def collect_product_ai_findings(repo: Repository, stack: dict) -> list[dict]:
    surfaces, context = stack["surfaces"], repo.nearest_context()
    results: list[dict] = []
    if not surfaces["end_user_product"]:
        results.append(finding("PROD-VALUE-001", "product-onboarding", "NOT_APPLICABLE", "MEDIUM", "HIGH", context, "No end-user signup/onboarding product surface was detected.", None))
    else:
        events = repo.grep([r"first[_ -]?value", r"activation[_ -]?event", r"onboarding[_ -]?completed", r"track\(['\"][^'\"]*(created|completed|activated)"])
        results.append(finding("PROD-VALUE-001", "product-onboarding", "PASS" if events else "NOT_VERIFIABLE", "MEDIUM", "MEDIUM", events or context + ["(searched onboarding/analytics code for first-value events)"], "A first-value/activation-oriented event signal was found; confirm it represents meaningful user value." if events else "A meaningful first-value definition may live in product analytics outside the repository.", None if events else "Name the first-value event and connect implementation and analytics evidence to it."))
    if not surfaces["agent_extensions"]:
        results.append(finding("AI-SUPPLY-001", "ai-usage", "NOT_APPLICABLE", "HIGH", "HIGH", context, "No agent extension, skill, MCP, or plugin surface was detected.", None))
    else:
        paths = [r for r in repo.relatives() if re.search(r"(SKILL\.md|CLAUDE\.md|AGENTS\.md|\.mcp\.json|\.claude-plugin/plugin\.json|\.codex-plugin/plugin\.json)$", r)]
        provenance = repo.grep([r"\b(version|commit|sha256|license|permission|network|provenance)\b"], paths=(i for i in repo.text_files if i.rel in paths))
        results.append(finding("AI-SUPPLY-001", "ai-usage", "PASS" if provenance else "PARTIAL", "HIGH", "MEDIUM", (provenance or paths)[:10], "Agent-extension configuration was found" + (" with provenance/permission review signals." if provenance else " without recognizable pinning or permission/provenance guidance."), None if provenance else "Document canonical sources, versions, permissions, network destinations, review ownership, and removal for external extensions."))
    if not surfaces["ai_usage"]:
        results.append(finding("AI-DATA-001", "ai-usage", "NOT_APPLICABLE", "HIGH", "HIGH", context, "No product or workflow AI-provider surface was detected.", None))
    else:
        dataflow = repo.grep([r"\b(retention|training|personal data|PII|redact|data flow|model provider|audio upload)\b"])
        results.append(finding("AI-DATA-001", "ai-usage", "PASS" if dataflow else "PARTIAL", "HIGH", "MEDIUM", dataflow or context, "AI usage was found" + (" with data-flow/privacy documentation signals." if dataflow else " without recognizable data-flow, retention, or sensitive-input documentation."), None if dataflow else "Document provider destinations, sensitive inputs, retention/training settings, user disclosure/consent, and local-versus-upload behavior."))
    promo = repo.grep([r"\b(10x|11x|best model|top[- ]level|unlimited|\$[0-9,]+.*(month|website)|one line of code)\b"])
    results.append(finding("AI-PROMO-001", "ai-usage", "NOT_VERIFIABLE" if promo else "NOT_APPLICABLE", "INFO", "HIGH" if promo else "MEDIUM", promo or context, "Promotional or subjective claims are advisory and excluded from the audit verdict." if promo else "No tracked promotional-claim signal was detected.", "Verify any material claim against a reproducible baseline before relying on it." if promo else None, advisory=True))
    return results


def collect_findings(repo: Repository, stack: dict) -> list[dict]:
    results: list[dict] = []
    for collector in (
        collect_development_findings,
        collect_security_findings,
        collect_reliability_findings,
        collect_product_ai_findings,
    ):
        results.extend(collector(repo, stack))
    return results


def render_text(report: dict) -> str:
    lines = [
        f"Target: {report['target']}",
        f"Verdict: {report['summary']['verdict']}",
        "Stack: " + ", ".join(report["stack"]["languages"] + report["stack"]["frameworks"]),
        "",
    ]
    for item in report["findings"]:
        lines.append(f"[{item['status']}] {item['check_id']} ({item['severity']}, {item['confidence']})")
        lines.append(f"  Evidence: {', '.join(item['evidence_paths'])}")
        lines.append(f"  Rationale: {item['rationale']}")
        if item["remediation"]:
            lines.append(f"  Remediation: {item['remediation']}")
    return "\n".join(lines)


def build_report(
    root: Path,
    max_total_text_bytes: int = 25_000_000,
    max_inventory_files: int = 100_000,
    max_text_candidates: int = 50_000,
) -> dict:
    repo = Repository(
        root,
        max_total_text_bytes=max_total_text_bytes,
        max_inventory_files=max_inventory_files,
        max_text_candidates=max_text_candidates,
    )
    stack = detect_stack(repo)
    findings = collect_findings(repo, stack)
    counts = {status: 0 for status in ("PASS", "MISSING", "PARTIAL", "NOT_APPLICABLE", "NOT_VERIFIABLE")}
    for item in findings:
        counts[item["status"]] += 1
    failures = [i for i in findings if not i["advisory"] and i["status"] in {"MISSING", "PARTIAL"}]
    return {
        "schema_version": 1,
        "target": str(repo.root),
        "read_only": True,
        "stack": stack,
        "findings": findings,
        "summary": {"counts": counts, "failing_check_ids": [i["check_id"] for i in failures], "verdict": "NEEDS_WORK" if failures else "PASS"},
        "limitations": [
            "Static repository evidence cannot prove runtime, provider-console, organizational, or production state.",
            "Secret scanning is bounded and redacts values; use a dedicated approved scanner for exhaustive history analysis.",
            f"Inventory is bounded to {repo.max_inventory_files} files and {repo.max_text_candidates} text candidates; truncation={str(repo.inventory_truncated).lower()}.",
            f"Text evidence is bounded to {repo.max_file_bytes} bytes per file and {repo.max_total_text_bytes} bytes per project; {repo.skipped_text_path_count} candidate file(s) were skipped.",
            "Agent review must inspect relevant evidence before presenting final findings.",
        ],
        "evidence_budget": {
            "max_file_bytes": repo.max_file_bytes,
            "max_total_text_bytes": repo.max_total_text_bytes,
            "max_inventory_files": repo.max_inventory_files,
            "max_text_candidates": repo.max_text_candidates,
            "inventoried_file_count": repo.inventoried_file_count,
            "text_candidate_count": repo.text_candidate_count,
            "inventory_truncated": repo.inventory_truncated,
            "scanned_text_bytes": repo.scanned_text_bytes,
            "skipped_text_paths": repo.skipped_text_paths,
            "skipped_text_path_count": repo.skipped_text_path_count,
        },
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Project root to inspect read-only")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--max-total-text-bytes", type=int, default=25_000_000,
                        help="Aggregate text evidence budget (default: 25000000)")
    parser.add_argument("--max-inventory-files", type=int, default=100_000,
                        help="Maximum inventoried files before traversal stops (default: 100000)")
    parser.add_argument("--max-text-candidates", type=int, default=50_000,
                        help="Maximum candidate text files before traversal stops (default: 50000)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.root.is_dir():
        print(f"error: project root is not a directory: {args.root}", file=sys.stderr)
        return 2
    if args.max_total_text_bytes < 1:
        print("error: --max-total-text-bytes must be positive", file=sys.stderr)
        return 2
    if args.max_inventory_files < 1 or args.max_text_candidates < 1:
        print("error: inventory limits must be positive", file=sys.stderr)
        return 2
    report = build_report(
        args.root,
        args.max_total_text_bytes,
        args.max_inventory_files,
        args.max_text_candidates,
    )
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
