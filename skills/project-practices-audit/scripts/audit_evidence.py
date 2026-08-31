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
class RubricCheck:
    check_id: str
    domain: str
    severity: str
    required_surfaces: tuple[str, ...]
    unavailable_rationale: str
    remediation: str | None


RUBRIC_CHECKS = (
    RubricCheck("DEV-SCOPE-001", "coding-ai", "MEDIUM", ("agent_extensions",), "Agent-instruction scope and consequential-action boundaries require review.", "Define project scope, verification expectations, and approval boundaries for consequential actions."),
    RubricCheck("DEV-TEST-001", "coding-ai", "HIGH", ("code",), "Test coverage requires project-specific inspection.", "Add representative automated tests and a repeatable test command."),
    RubricCheck("DEV-CI-001", "coding-ai", "MEDIUM", ("code",), "CI validation requires project-specific inspection.", "Run applicable validation in CI or document the external gate."),
    RubricCheck("DEV-DEPS-001", "coding-ai", "MEDIUM", (), "Dependency reproducibility requires manifest inspection.", "Commit the ecosystem's supported lock or checksum file."),
    RubricCheck("DEV-STATE-001", "coding-ai", "LOW", ("agent_extensions",), "Persistent agent-state and acceptance criteria require workflow review.", "Document concise state and acceptance criteria for long-running agent work when applicable."),
    RubricCheck("SEC-AUTHZ-001", "application-security", "CRITICAL", ("network_service", "authentication"), "Authorization correctness requires route and data-flow inspection.", "Authorize protected objects server-side and add negative cross-user tests."),
    RubricCheck("SEC-SESS-001", "application-security", "HIGH", ("authentication",), "Session storage and runtime cookie attributes cannot be established from generic static signals.", "Verify expiring sessions and secure, HttpOnly, SameSite cookie or platform-storage behavior."),
    RubricCheck("SEC-AUTHN-001", "application-security", "HIGH", ("network_service", "authentication"), "Authentication abuse controls and recovery behavior require endpoint and provider review.", "Add server-side abuse controls and safe account-recovery tests."),
    RubricCheck("SEC-RLS-001", "application-security", "CRITICAL", ("supabase",), "Supabase RLS and grant coverage require migration and role-test inspection.", "Enable and test least-privilege RLS and grants for every exposed table."),
    RubricCheck("SEC-WEBHOOK-001", "application-security", "CRITICAL", ("webhooks",), "Webhook authenticity and retry behavior require handler inspection.", "Verify raw-body signatures before effects and make repeated delivery safe."),
    RubricCheck("SEC-API-001", "application-security", "HIGH", ("network_service",), "API authentication, validation, authorization, and resource bounds require route inspection.", "Review public API boundaries and add negative and resource-limit tests."),
    RubricCheck("SEC-EDGE-001", "application-security", "MEDIUM", ("network_service", "infrastructure_deployment"), "Deployed edge and origin exposure are not established by repository heuristics.", "Document the deployed origin and edge threat model and its controls."),
    RubricCheck("SEC-MOBILE-001", "application-security", "HIGH", ("mobile",), "Native storage, deep links, and OAuth behavior require platform-specific inspection.", "Review platform secret storage, deep links, and OAuth PKCE where applicable."),
    RubricCheck("SEC-SECRETS-001", "application-security", "CRITICAL", (), "Committed-secret safety requires bounded repository scanning.", "Remove and rotate committed credentials and use secret injection."),
    RubricCheck("REL-RPO-001", "data-reliability", "HIGH", ("durable_data",), "Owned, measurable recovery objectives were not established.", "Document owned RPO and RTO time targets for critical durable data."),
    RubricCheck("REL-BACKUP-001", "data-reliability", "CRITICAL", ("durable_data",), "Backup isolation and PITR configuration commonly live outside the repository.", "Verify backup or PITR configuration against the stated RPO and isolate it from the primary failure domain."),
    RubricCheck("REL-RESTORE-001", "data-reliability", "HIGH", ("durable_data",), "Timed restoration evidence was not established.", "Run and record an isolated restore drill against the stated RTO."),
    RubricCheck("REL-MIGRATE-001", "data-reliability", "HIGH", ("durable_data",), "Migration retry safety and representative validation require migration inspection.", "Exercise reviewable migrations in CI or staging and document retry and rollback behavior."),
    RubricCheck("REL-OBS-001", "data-reliability", "HIGH", ("durable_data",), "Critical data-path and recovery alerting may be provider-owned.", "Verify alerts for backup, archive, queue, and critical data-path failures."),
    RubricCheck("TEN-ISO-001", "multitenancy", "CRITICAL", ("multitenant",), "Tenant enforcement and negative isolation tests require data-boundary inspection.", "Centralize tenant scoping and add negative cross-tenant read and write tests."),
    RubricCheck("TEN-EXT-001", "multitenancy", "MEDIUM", ("multitenant",), "Tenant-specific extension behavior requires schema and lifecycle inspection.", "Validate custom tenant attributes across limits, indexes, migrations, exports, and deletion."),
    RubricCheck("TEN-NOISY-001", "multitenancy", "HIGH", ("multitenant",), "Per-tenant resource boundaries require workload and runtime inspection.", "Bound and observe expensive shared work per tenant where applicable."),
    RubricCheck("TEN-MIGRATE-001", "multitenancy", "HIGH", ("multitenant",), "Fleet or per-tenant migration behavior requires direct implementation evidence.", "Make applicable tenant migrations resumable, observable, retry-safe, and rolling-deploy compatible."),
    RubricCheck("INF-DEPLOY-001", "infrastructure-deployment", "HIGH", ("infrastructure_deployment",), "Deployment and rollback evidence require pipeline inspection.", "Document and test deployment and return to a known-good release."),
    RubricCheck("INF-SECRET-001", "infrastructure-deployment", "CRITICAL", ("infrastructure_deployment",), "Runtime secret injection and rotation are commonly provider-owned.", "Verify runtime secret injection, ownership, and rotation without committing values."),
    RubricCheck("INF-NET-001", "infrastructure-deployment", "HIGH", ("infrastructure_deployment",), "Deployed network exposure cannot be established from generic static signals.", "Restrict public exposure to required services and protect stateful and administrative surfaces."),
    RubricCheck("INF-PATCH-001", "infrastructure-deployment", "HIGH", ("infrastructure_deployment",), "Runtime and host update strategy requires deployment-specific inspection.", "Document maintained runtime or image replacement and host patch ownership."),
    RubricCheck("INF-OBS-001", "infrastructure-deployment", "HIGH", ("infrastructure_deployment",), "Production service telemetry and alerts may live outside the repository.", "Verify logs, metrics, and alerts for availability, capacity, authentication, and critical health."),
    RubricCheck("INF-TLS-001", "infrastructure-deployment", "HIGH", ("network_service", "infrastructure_deployment"), "TLS termination and renewal ownership may be provider-managed.", "Verify public TLS termination and renewal ownership."),
    RubricCheck("PROD-VALUE-001", "product-onboarding", "MEDIUM", ("end_user_product",), "Meaningful first value may be defined in external product analytics.", "Name and instrument a meaningful first-value event."),
    RubricCheck("PROD-FLOW-001", "product-onboarding", "LOW", ("end_user_product",), "Core-action onboarding flow requires direct route and UI inspection.", "Remove unnecessary blockers before the user's core action."),
    RubricCheck("PROD-DISCLOSE-001", "product-onboarding", "LOW", ("end_user_product",), "Progressive disclosure requires qualitative UI inspection.", "Keep essential capability visible while deferring advanced complexity."),
    RubricCheck("PROD-REENGAGE-001", "product-onboarding", "MEDIUM", ("end_user_product",), "Lifecycle re-engagement triggers and consent controls require product-flow inspection.", "Tie re-engagement to created value and respect preferences, time zones, and data minimization."),
    RubricCheck("PROD-MEASURE-001", "product-onboarding", "LOW", ("end_user_product",), "Onboarding and retained-use measurement may live outside the repository.", "Distinguish first value from retained use in product measurement."),
    RubricCheck("AI-DATA-001", "ai-usage", "HIGH", ("ai_usage",), "AI data destinations and handling require provider and product-flow inspection.", "Document providers, sensitive inputs, retention, training settings, and disclosure or consent."),
    RubricCheck("AI-KEY-001", "ai-usage", "CRITICAL", ("ai_usage",), "AI credential scope and rotation require configuration inspection.", "Keep provider credentials server-side, scoped, injected, and rotatable."),
    RubricCheck("AI-OUTPUT-001", "ai-usage", "HIGH", ("ai_usage",), "Consequential AI output boundaries require call-site inspection.", "Validate and bound model output before consequential side effects, with review and idempotency where needed."),
    RubricCheck("AI-EVAL-001", "ai-usage", "MEDIUM", ("ai_usage",), "Product-critical AI evaluation coverage requires executable behavior inspection.", "Add representative, versioned regression evaluations for product-critical AI behavior."),
    RubricCheck("AI-SUPPLY-001", "ai-usage", "HIGH", ("agent_extensions",), "Agent-extension provenance, pinning, and permissions require configuration inspection.", "Pin external extensions and document sources, permissions, network destinations, ownership, and removal."),
    RubricCheck("AI-PROMO-001", "ai-usage", "INFO", (), "Promotional claims require independent reproduction.", None),
)


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
        source = self.text_files if paths is None else paths
        for item in source:
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


AGENT_INSTRUCTION_PATH_RE = re.compile(
    r"(^|/)(\.claude|\.codex|\.agents)(/|$)|"
    r"(^|/)(SKILL\.md|CLAUDE\.md|AGENTS\.md)$",
    re.I,
)
EXTENSION_PATH_RE = re.compile(
    r"(^|/)(\.mcp\.json|SKILL\.md|CLAUDE\.md|AGENTS\.md|"
    r"\.claude-plugin/plugin\.json|\.codex-plugin/plugin\.json|"
    r"\.claude/settings[^/]*\.json)$",
    re.I,
)
TIME_TARGET = r"\d+(?:\.\d+)?\s*[- ]?\s*(?:ms|milliseconds?|s|seconds?|m|minutes?|h|hours?|d|days?)"
RUNNER_COMMANDS = {"npx", "pnpx", "bunx", "uvx", "pipx"}
RUNNER_VALUE_OPTIONS = {
    "-c", "--call", "--cache", "--package", "-p", "--python", "--from",
}


def operational_text_files(repo: Repository) -> list[TextFile]:
    """Exclude agent instruction libraries when looking for product operations evidence."""
    return [item for item in repo.text_files if not AGENT_INSTRUCTION_PATH_RE.search(item.rel)]


def first_line_containing(item: TextFile, value: str) -> str:
    for line_no, line in enumerate(item.lines, 1):
        if value in line:
            return f"{item.rel}:{line_no}"
    return item.rel


def is_placeholder_secret(value: str) -> bool:
    normalized = value.lower().strip()
    placeholders = (
        "changeme", "change-me", "dummy", "example", "fake", "fixture",
        "placeholder", "replace-me", "replace_me", "sample", "test",
        "your-", "your_",
    )
    return normalized and (
        all(character == "x" for character in normalized)
        or any(
            normalized == marker
            or normalized.startswith(f"{marker}-")
            or normalized.startswith(f"{marker}_")
            for marker in placeholders
        )
    )


def exact_runner_package_pin(token: str) -> bool:
    """Accept immutable npm-style versions or full Git commit references."""
    if re.search(r"#[0-9a-f]{40,64}$", token, re.I):
        return True
    python_pin = re.search(r"==(?P<version>\d+\.\d+\.\d+(?:[0-9A-Za-z.-]+)?)$", token)
    if python_pin:
        return True
    if token.startswith("@"):
        separator = token.rfind("@")
        if separator <= 0:
            return False
        version = token[separator + 1:]
    else:
        if "@" not in token:
            return False
        version = token.rsplit("@", 1)[1]
    return bool(re.fullmatch(r"v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", version))


def runner_package(args: Sequence[str]) -> str | None:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--":
            return None
        if arg in RUNNER_VALUE_OPTIONS:
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        return arg
    return None


def external_runner_packages(command: str, args: Sequence[str]) -> list[str]:
    tokens = [command, *args]
    packages: list[str] = []
    for index, token in enumerate(tokens):
        executable = Path(token).name
        tail = tokens[index + 1:]
        if executable in RUNNER_COMMANDS:
            explicit: list[str] = []
            for option_index, option in enumerate(tail):
                if option.startswith("--package="):
                    explicit.append(option.split("=", 1)[1])
                elif option in {"--package", "-p", "--from"} and option_index + 1 < len(tail):
                    explicit.append(tail[option_index + 1])
            if explicit:
                packages.extend(explicit)
            else:
                package = runner_package(tail)
                if executable == "pipx" and package == "run":
                    package = runner_package(tail[tail.index("run") + 1:])
                if package:
                    packages.append(package)
        elif executable in {"pnpm", "yarn"}:
            subcommand = runner_package(tail)
            if subcommand == "dlx":
                dlx_index = tail.index("dlx")
                package = runner_package(tail[dlx_index + 1:])
                if package:
                    packages.append(package)
        elif executable == "npm":
            subcommand = runner_package(tail)
            if subcommand in {"exec", "x"}:
                exec_index = tail.index(subcommand)
                exec_tail = tail[exec_index + 1:]
                explicit = [
                    option.split("=", 1)[1]
                    for option in exec_tail
                    if option.startswith("--package=")
                ]
                for option_index, option in enumerate(exec_tail):
                    if option in {"--package", "-p"} and option_index + 1 < len(exec_tail):
                        explicit.append(exec_tail[option_index + 1])
                if explicit:
                    packages.extend(explicit)
                else:
                    package = runner_package(exec_tail)
                    if package is None and "--" in exec_tail:
                        package = runner_package(exec_tail[exec_tail.index("--") + 1:])
                    if package:
                        packages.append(package)
    return list(dict.fromkeys(packages))


def unpinned_mcp_evidence(repo: Repository) -> list[str]:
    evidence: list[str] = []
    for item in repo.text_files:
        if Path(item.rel).name != ".mcp.json":
            continue
        try:
            document = json.loads(item.text)
        except json.JSONDecodeError:
            continue
        servers = document.get("mcpServers", {}) if isinstance(document, dict) else {}
        if not isinstance(servers, dict):
            continue
        for server in servers.values():
            if not isinstance(server, dict):
                continue
            command = server.get("command")
            args = server.get("args", [])
            if not isinstance(command, str) or not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                continue
            for package in external_runner_packages(command, args):
                if not exact_runner_package_pin(package):
                    evidence.append(first_line_containing(item, package))
                    break
    return sorted(set(evidence))


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
    assignment_re = re.compile(
        r"(?i)['\"]?\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|secret|token|password)\b['\"]?"
        r"\s*[:=]\s*(?P<quote>['\"])(?P<value>[A-Za-z0-9_./+=:@-]{16,})(?P=quote)"
    )
    env_assignment_re = re.compile(
        r"(?i)^\s*(?:[A-Z0-9_]*(?:API_KEY|CLIENT_SECRET|ACCESS_TOKEN|AUTH_TOKEN|SECRET|PASSWORD|TOKEN))"
        r"\s*=\s*(?P<value>[A-Za-z0-9_./+=:@-]{16,})\s*(?:#.*)?$"
    )
    for item in repo.text_files:
        if Path(item.rel).name.endswith((".example", ".sample")) or "/fixtures/" in f"/{item.rel}/":
            continue
        for line_no, line in enumerate(item.lines, 1):
            literal = assignment_re.search(line)
            env_literal = env_assignment_re.search(line) if Path(item.rel).suffix.lower() in {".env", ".conf", ".properties"} else None
            value = literal.group("value") if literal else env_literal.group("value") if env_literal else None
            if private_key_re.search(line) or (value is not None and not is_placeholder_secret(value)):
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
        operational = operational_text_files(repo)
        rpo = repo.grep([
            rf"\bRPO\b.{{0,32}}(?:is|of|target|objective|[:=]|<=?|≤)\s*{TIME_TARGET}\b",
            rf"\b{TIME_TARGET}\s+(?:maximum\s+)?RPO\b",
            rf"\brecovery point objective\b.{{0,32}}(?:is|of|target|[:=]|<=?|≤)\s*{TIME_TARGET}\b",
        ], paths=operational)
        rto = repo.grep([
            rf"\bRTO\b.{{0,32}}(?:is|of|target|objective|[:=]|<=?|≤)\s*{TIME_TARGET}\b",
            rf"\b{TIME_TARGET}\s+(?:maximum\s+)?RTO\b",
            rf"\brecovery time objective\b.{{0,32}}(?:is|of|target|[:=]|<=?|≤)\s*{TIME_TARGET}\b",
        ], paths=operational)
        objective_mentions = repo.grep([r"\bRPO\b", r"\bRTO\b", r"recovery (point|time) objective"], paths=operational)
        if rpo and rto:
            results.append(finding("REL-RPO-001", "data-reliability", "PASS", "HIGH", "HIGH", sorted(set(rpo + rto)), "Explicit RPO and RTO time targets were found.", None))
        elif rpo or rto:
            results.append(finding("REL-RPO-001", "data-reliability", "PARTIAL", "HIGH", "HIGH", sorted(set(rpo + rto)), "Only one measurable recovery objective was found.", "Document both owned RPO and RTO time targets for critical durable data."))
        else:
            results.append(finding("REL-RPO-001", "data-reliability", "NOT_VERIFIABLE", "HIGH", "MEDIUM", objective_mentions or context + ["(searched for measurable RPO/RTO time targets)"], "Recovery-objective terminology was found without measurable targets." if objective_mentions else "Recovery objectives may be maintained outside the repository.", "Document owned RPO and RTO time targets and link backup and recovery design to them."))

        recovery_docs = [
            item for item in operational
            if re.search(r"(^|/)(?:[^/]*(?:recovery|restore|backup|runbook|disaster)[^/]*)\.(?:md|txt|ya?ml|json|toml|sh|py)$", item.rel, re.I)
        ]
        restore_guidance = repo.grep([
            r"\brestore (?:runbook|procedure|steps?|command|workflow)\b",
            r"\brecovery (?:runbook|procedure)\b",
        ], paths=recovery_docs)
        restore_guidance += repo.grep([
            r"\brestore\b.{0,100}\b(?:into (?:an )?isolated|from (?:the )?(?:backup|snapshot)|verify|validation|critical (?:read|write|path))\b",
            r"\brecovery (?:runbook|procedure)\b",
        ], paths=operational)
        restore_guidance = sorted(set(restore_guidance))
        drill = repo.grep([
            r"\b(?:restore drill|restore test|recovery exercise)\b.{0,120}\b(?:completed|passed|failed|measured|within (?:the )?target)\b",
            r"\b(?:last|most recent)\b.{0,80}\b(?:restore drill|restore test|recovery exercise)\b",
            rf"\bmeasured RTO\b.{{0,24}}(?:[:=]|was|of)\s*{TIME_TARGET}\b",
        ], paths=operational)
        restore_mentions = repo.grep([r"\brestore\b", r"recovery (?:drill|exercise)"], paths=operational)
        if restore_guidance and drill:
            results.append(finding("REL-RESTORE-001", "data-reliability", "PASS", "HIGH", "HIGH", sorted(set(restore_guidance + drill)), "A restore procedure and completed or measured drill evidence were found.", None))
        elif restore_guidance:
            results.append(finding("REL-RESTORE-001", "data-reliability", "PARTIAL", "HIGH", "MEDIUM", restore_guidance, "Restore guidance exists but no completed or measured drill evidence was found.", "Run an isolated restore drill, verify critical paths, measure against RTO, and record the result."))
        else:
            results.append(finding("REL-RESTORE-001", "data-reliability", "NOT_VERIFIABLE", "HIGH", "MEDIUM", restore_mentions or context + ["(searched for restore procedure and completed drill evidence)"], "Restore terminology was found without a recognizable procedure or completed drill." if restore_mentions else "No repository restore evidence was found; recovery records may be external.", "Link or add the restore runbook and recent drill evidence without exposing sensitive operational values."))
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
        paths = [r for r in repo.relatives() if EXTENSION_PATH_RE.search(r)]
        extension_files = [item for item in repo.text_files if item.rel in paths]
        provenance = repo.grep([r"\b(version|commit|sha(?:256)?|license|provenance|canonical source)\b"], paths=extension_files)
        permissions = repo.grep([r"\b(permission|allowed tools?|network destinations?|sandbox|read[- ]only)\b"], paths=extension_files)
        unpinned = unpinned_mcp_evidence(repo)
        if unpinned:
            results.append(finding("AI-SUPPLY-001", "ai-usage", "PARTIAL", "HIGH", "HIGH", unpinned[:10], "At least one externally executed MCP package is not pinned to an immutable version or commit.", "Pin every runner-installed MCP package to an exact version or full commit, then document permissions, network destinations, review ownership, and removal."))
        elif provenance and permissions:
            results.append(finding("AI-SUPPLY-001", "ai-usage", "PASS", "HIGH", "MEDIUM", sorted(set(provenance + permissions))[:10], "Agent-extension configuration has recognizable provenance and permission-review signals, with no floating MCP runner package detected.", None))
        else:
            results.append(finding("AI-SUPPLY-001", "ai-usage", "PARTIAL", "HIGH", "MEDIUM", (provenance + permissions or paths)[:10], "Agent-extension configuration lacks complete provenance and permission-review evidence.", "Document canonical sources, exact versions or commits, permissions, network destinations, review ownership, and removal for external extensions."))
    if not surfaces["ai_usage"]:
        results.append(finding("AI-DATA-001", "ai-usage", "NOT_APPLICABLE", "HIGH", "HIGH", context, "No product or workflow AI-provider surface was detected.", None))
    else:
        dataflow = repo.grep([r"\b(retention|training|personal data|PII|redact|data flow|model provider|audio upload)\b"])
        results.append(finding("AI-DATA-001", "ai-usage", "PASS" if dataflow else "PARTIAL", "HIGH", "MEDIUM", dataflow or context, "AI usage was found" + (" with data-flow/privacy documentation signals." if dataflow else " without recognizable data-flow, retention, or sensitive-input documentation."), None if dataflow else "Document provider destinations, sensitive inputs, retention/training settings, user disclosure/consent, and local-versus-upload behavior."))
    promo = repo.grep([r"\b(10x|11x|best model|top[- ]level|unlimited|\$[0-9,]+.*(month|website)|one line of code)\b"])
    results.append(finding("AI-PROMO-001", "ai-usage", "NOT_VERIFIABLE" if promo else "NOT_APPLICABLE", "INFO", "HIGH" if promo else "MEDIUM", promo or context, "Promotional or subjective claims are advisory and excluded from the audit verdict." if promo else "No tracked promotional-claim signal was detected.", "Verify any material claim against a reproducible baseline before relying on it." if promo else None, advisory=True))
    return results


def complete_rubric_coverage(repo: Repository, stack: dict, analyzed: Sequence[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for item in analyzed:
        check_id = item["check_id"]
        if check_id in by_id:
            raise RuntimeError(f"duplicate analyzer finding: {check_id}")
        by_id[check_id] = item

    known_ids = {check.check_id for check in RUBRIC_CHECKS}
    unexpected = sorted(set(by_id) - known_ids)
    if unexpected:
        raise RuntimeError(f"analyzer emitted unknown rubric checks: {', '.join(unexpected)}")

    results: list[dict] = []
    surfaces = stack["surfaces"]
    context = repo.nearest_context()
    for check in RUBRIC_CHECKS:
        if check.check_id in by_id:
            results.append(by_id[check.check_id])
            continue
        applicable = all(surfaces.get(surface, False) for surface in check.required_surfaces)
        if not applicable:
            missing_surfaces = ", ".join(
                surface for surface in check.required_surfaces if not surfaces.get(surface, False)
            )
            results.append(finding(
                check.check_id,
                check.domain,
                "NOT_APPLICABLE",
                check.severity,
                "HIGH",
                context,
                f"Required project surface was not detected: {missing_surfaces}.",
                None,
                advisory=check.check_id == "AI-PROMO-001",
            ))
            continue
        results.append(finding(
            check.check_id,
            check.domain,
            "NOT_VERIFIABLE",
            check.severity,
            "MEDIUM",
            context + ["(no sufficient deterministic evidence; agent inspection required)"],
            check.unavailable_rationale,
            check.remediation,
            advisory=check.check_id == "AI-PROMO-001",
        ))
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
    return complete_rubric_coverage(repo, stack, results)


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
