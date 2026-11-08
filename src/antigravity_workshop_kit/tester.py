"""Bash snippet syntax extractor, static best-practice auditor, and GCP smoke tester."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess

BASH_BLOCK_PATTERN = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)
API_HOST_PATTERN = re.compile(r"\b([a-z0-9-]+\.googleapis\.com)\b")
ALLOWED_PUBLIC_APIS = frozenset(
    {
        "aiplatform.googleapis.com",
        "serviceusage.googleapis.com",
        "cloudresourcemanager.googleapis.com",
        "cloudaicompanion.googleapis.com",
        "cloudidentity.googleapis.com",
        "billingbudgets.googleapis.com",
        "orgpolicy.googleapis.com",
        "run.googleapis.com",
        "artifactregistry.googleapis.com",
        "cloudbuild.googleapis.com",
        "storage.googleapis.com",
    }
)


@dataclass
class ValidationResult:
    """Structured result of testing a rendered workshop guide."""

    passed: bool
    bash_blocks_checked: int = 0
    syntax_errors: list[str] = field(default_factory=list)
    static_violations: list[str] = field(default_factory=list)
    smoke_test_errors: list[str] = field(default_factory=list)

    def all_errors(self) -> list[str]:
        """Return all collected error messages across categories."""
        return [
            *self.syntax_errors,
            *self.static_violations,
            *self.smoke_test_errors,
        ]


def extract_bash_blocks(markdown_text: str) -> list[str]:
    """Extract all fenced ```bash ... ``` code blocks from a Markdown document."""
    return [match.group(1) for match in BASH_BLOCK_PATTERN.finditer(markdown_text)]


def sanitize_placeholders_for_syntax_check(snippet: str) -> str:
    """Replace angle-bracket user placeholders (<N>, <BILLING_ACCOUNT_ID>, etc.) for bash -n."""
    sanitized = snippet
    sanitized = sanitized.replace("<BILLING_ACCOUNT_ID>", "012345-6789AB-CDEF01")
    sanitized = sanitized.replace("<FOLDER_ID>", "123456789012")
    sanitized = sanitized.replace("<NN>", "01")
    sanitized = sanitized.replace("<N>", "1")
    # Replace any remaining <PLACEHOLDER> tokens with a safe alphanumeric string
    sanitized = re.sub(r"<[A-Za-z0-9_-]+>", "placeholder_val", sanitized)
    return sanitized


def check_bash_syntax(snippets: list[str]) -> list[str]:
    """Validate each bash block using 'bash -n' and return any syntax error messages."""
    errors: list[str] = []
    for index, snippet in enumerate(snippets, start=1):
        sanitized = sanitize_placeholders_for_syntax_check(snippet)
        proc = subprocess.run(
            ["bash", "-n"],
            input=sanitized,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or f"bash -n exited with code {proc.returncode}"
            errors.append(f"Bash block #{index} syntax error: {err_msg}")
    return errors


def check_static_rules(
    markdown_text: str,
    snippets: list[str],
    auth_mode: str = "vertex_paygo",
) -> list[str]:
    """Run static best-practice audits against the guide and its bash blocks."""
    violations: list[str] = []
    combined_bash = "\n".join(snippets)

    # 1. Assert all referenced *.googleapis.com endpoints belong to the public allowlist
    referenced_apis = sorted(set(API_HOST_PATTERN.findall(markdown_text)))
    for api_host in referenced_apis:
        if api_host not in ALLOWED_PUBLIC_APIS:
            violations.append(
                f"Unapproved API endpoint '{api_host}' found in setup guide."
            )

    # 2. Assert client region is instructed as Global / global
    has_ui_global = "**`Global`**" in markdown_text or "`Global`" in markdown_text
    has_cli_global = "> global" in markdown_text or "region: global" in markdown_text.lower()
    if not (has_ui_global and has_cli_global):
        violations.append(
            "Setup guide must explicitly instruct selecting 'Global' (UI) and 'global' (CLI) region."
        )

    # 3. Assert gcloud auth login --update-adc is present for single-step authentication
    if "gcloud auth login --update-adc" not in combined_bash:
        violations.append(
            "Missing 'gcloud auth login --update-adc' in bash snippets for single-step browser authentication."
        )

    # 4. Mode-specific IAM role checks
    if auth_mode == "vertex_paygo":
        if "roles/aiplatform.user" not in combined_bash:
            violations.append(
                "vertex_paygo mode requires granting 'roles/aiplatform.user' in bash snippets."
            )
        if "roles/serviceusage.serviceUsageConsumer" not in combined_bash:
            violations.append(
                "vertex_paygo mode requires granting 'roles/serviceusage.serviceUsageConsumer' in bash snippets."
            )
    elif auth_mode == "gemini_enterprise":
        if "roles/cloudaicompanion.user" not in combined_bash:
            violations.append(
                "gemini_enterprise mode requires granting 'roles/cloudaicompanion.user' in bash snippets."
            )
        if "roles/serviceusage.serviceUsageConsumer" not in combined_bash:
            violations.append(
                "gemini_enterprise mode requires granting 'roles/serviceusage.serviceUsageConsumer' in bash snippets."
            )

    return violations


def run_live_gcp_smoke_test(
    project_id: str,
    auth_mode: str = "vertex_paygo",
) -> list[str]:
    """Verify live GCP project reachability and required API status via gcloud."""
    errors: list[str] = []
    desc_proc = subprocess.run(
        [
            "gcloud",
            "projects",
            "describe",
            project_id,
            "--format=value(projectId)",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if desc_proc.returncode != 0:
        detail = desc_proc.stderr.strip() or "project unreachable"
        errors.append(f"Live GCP project check failed for '{project_id}': {detail}")
        return errors

    services_proc = subprocess.run(
        [
            "gcloud",
            "services",
            "list",
            "--enabled",
            f"--project={project_id}",
            "--format=value(config.name)",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if services_proc.returncode != 0:
        detail = services_proc.stderr.strip() or "unable to list enabled services"
        errors.append(f"Live GCP services check failed for '{project_id}': {detail}")
        return errors

    enabled_services = {
        line.strip()
        for line in services_proc.stdout.splitlines()
        if line.strip()
    }
    required_apis = {"serviceusage.googleapis.com", "cloudaicompanion.googleapis.com"}
    if auth_mode == "vertex_paygo":
        required_apis.add("aiplatform.googleapis.com")

    missing = sorted(required_apis - enabled_services)
    if missing:
        errors.append(
            f"Live GCP project '{project_id}' is missing required enabled APIs: {', '.join(missing)}"
        )

    return errors


def validate_guide_file(
    guide_path: Path,
    auth_mode: str = "vertex_paygo",
    live_project: str | None = None,
) -> ValidationResult:
    """Validate a generated Markdown setup guide file for bash syntax, static rules, and optional live GCP smoke checks."""
    if not guide_path.exists():
        return ValidationResult(
            passed=False,
            static_violations=[f"Setup guide file not found: {guide_path}"],
        )

    markdown_text = guide_path.read_text(encoding="utf-8")
    snippets = extract_bash_blocks(markdown_text)

    syntax_errors = check_bash_syntax(snippets)
    static_violations = check_static_rules(markdown_text, snippets, auth_mode=auth_mode)
    if not snippets:
        static_violations.append("No ```bash ... ``` code blocks found in setup guide.")

    smoke_errors: list[str] = []
    if live_project:
        smoke_errors = run_live_gcp_smoke_test(live_project, auth_mode=auth_mode)

    passed = not (syntax_errors or static_violations or smoke_errors)
    return ValidationResult(
        passed=passed,
        bash_blocks_checked=len(snippets),
        syntax_errors=syntax_errors,
        static_violations=static_violations,
        smoke_test_errors=smoke_errors,
    )
