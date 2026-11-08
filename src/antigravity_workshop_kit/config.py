"""Configuration schema and state management for Antigravity Workshop Kit."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(".workshop-config.json")
VALID_AUTH_MODES = ("vertex_paygo", "gemini_enterprise")
DEFAULT_ALLOWED_MODELS = [
    "publishers/google/models/gemini-4-argon:predict",
    "publishers/google/models/gemini-3.8-flash:predict",
    "publishers/anthropic/models/claude-opus-5.5:predict",
    "publishers/anthropic/models/claude-sonnet-5.5:predict",
]


@dataclass
class WorkshopConfig:
    """Configuration state stored in .workshop-config.json."""

    organization: str = "Workshop"
    auth_mode: str = "vertex_paygo"
    team_count: int = 5
    project_prefix: str = "workshop-team"
    billing_account_id: str = "<BILLING_ACCOUNT_ID>"
    folder_id: str = ""
    region: str = "global"
    compute_region: str = "us-central1"
    budget_alert_usd: int = 250
    rate_limit_rpm: int = 150
    group_email_pattern: str = "agy-workshop-team{NN}@example.com"
    enable_cloud_resources: bool = True
    enable_model_restrictions: bool = True
    allowed_models: list[str] = field(
        default_factory=lambda: list(DEFAULT_ALLOWED_MODELS)
    )
    output_filename: str = "antigravity_setup_guide.md"

    def validate(self) -> None:
        """Validate configuration fields and raise ValueError on invalid values."""
        if not self.organization or not self.organization.strip():
            raise ValueError("organization must be a non-empty string.")
        if self.auth_mode not in VALID_AUTH_MODES:
            raise ValueError(
                f"auth_mode must be one of {VALID_AUTH_MODES}, got '{self.auth_mode}'."
            )
        if self.team_count < 1:
            raise ValueError(f"team_count must be >= 1, got {self.team_count}.")
        if not self.project_prefix or not self.project_prefix.strip():
            raise ValueError("project_prefix must be a non-empty string.")
        if self.region.lower() != "global":
            raise ValueError(
                f"region must be 'global' for Antigravity Gemini endpoints, got '{self.region}'."
            )
        if self.budget_alert_usd < 1:
            raise ValueError(
                f"budget_alert_usd must be >= 1, got {self.budget_alert_usd}."
            )
        if self.rate_limit_rpm < 1:
            raise ValueError(
                f"rate_limit_rpm must be >= 1, got {self.rate_limit_rpm}."
            )
        if not isinstance(self.allowed_models, list):
            raise ValueError("allowed_models must be a list of model identifiers.")
        for model in self.allowed_models:
            if not isinstance(model, str) or not model.strip():
                raise ValueError("Each item in allowed_models must be a non-empty string.")

    @staticmethod
    def format_team_pattern(pattern: str, team_num: int) -> str:
        """Format a string containing {N} or {NN} placeholders for a given team number."""
        rendered = pattern.replace("{NN}", f"{team_num:02d}")
        rendered = rendered.replace("{N}", str(team_num))
        return rendered

    def project_id(self, team_num: int) -> str:
        """Return the concrete project ID for a 1-based team number (zero-prefixed by default)."""
        if "{N}" in self.project_prefix or "{NN}" in self.project_prefix:
            return self.format_team_pattern(self.project_prefix, team_num)
        return f"{self.project_prefix}{team_num:02d}"

    def project_id_placeholder(self) -> str:
        """Return a human-readable placeholder project ID (e.g. workshop-team<NN>)."""
        if "{N}" in self.project_prefix or "{NN}" in self.project_prefix:
            return (
                self.project_prefix.replace("{NN}", "<NN>").replace("{N}", "<N>")
            )
        return f"{self.project_prefix}<NN>"

    def bash_project_id_expr(self) -> str:
        """Return the bash loop expression for project ID (using ${N} or ${NN})."""
        if "{N}" in self.project_prefix or "{NN}" in self.project_prefix:
            return (
                self.project_prefix.replace("{NN}", "${NN}").replace("{N}", "${N}")
            )
        return f"{self.project_prefix}${{NN}}"

    def group_email(self, team_num: int) -> str:
        """Return the concrete group email for a 1-based team number."""
        return self.format_team_pattern(self.group_email_pattern, team_num)

    def bash_group_email_expr(self) -> str:
        """Return the bash loop expression for group email (using ${N} or ${NN})."""
        return (
            self.group_email_pattern.replace("{NN}", "${NN}").replace("{N}", "${N}")
        )

    def email_domain(self) -> str:
        """Extract the domain suffix from group_email_pattern."""
        if "@" in self.group_email_pattern:
            return self.group_email_pattern.split("@", 1)[1]
        return "example.com"

    def team_projects(self) -> list[str]:
        """Return all concrete team project IDs."""
        return [self.project_id(i) for i in range(1, self.team_count + 1)]

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration to a dictionary."""
        return asdict(self)

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> Path:
        """Validate and persist configuration to JSON."""
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> WorkshopConfig:
        """Load configuration from JSON file, falling back to example template or defaults if absent."""
        if not path.exists():
            example_path = path.parent / "workshop-config.example.json"
            if path == DEFAULT_CONFIG_PATH and example_path.exists():
                try:
                    raw_data = json.loads(example_path.read_text(encoding="utf-8"))
                    return cls.from_dict(raw_data)
                except Exception:
                    pass
            config = cls()
            config.validate()
            return config
        raw_data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(raw_data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkshopConfig:
        """Construct WorkshopConfig from a dictionary."""
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_keys and v is not None}
        if "allowed_models" in filtered:
            val = filtered["allowed_models"]
            if isinstance(val, str):
                filtered["allowed_models"] = [
                    m.strip() for m in val.split(",") if m.strip()
                ]
            elif isinstance(val, (list, tuple)):
                filtered["allowed_models"] = [
                    str(m).strip() for m in val if str(m).strip()
                ]
        config = cls(**filtered)
        config.validate()
        return config


OPTION_DESCRIPTIONS: dict[str, dict[str, Any]] = {
    "organization": {
        "flag": "--organization",
        "type": "string",
        "default": "Workshop",
        "description": "Organization name.",
    },
    "auth_mode": {
        "flag": "--auth-mode",
        "type": "string",
        "choices": list(VALID_AUTH_MODES),
        "default": "vertex_paygo",
        "description": "Licensing/auth model ('vertex_paygo' or 'gemini_enterprise').",
    },
    "team_count": {
        "flag": "--teams",
        "type": "integer",
        "default": 5,
        "description": "Number of team projects to provision.",
    },
    "project_prefix": {
        "flag": "--prefix",
        "type": "string",
        "default": "workshop-team",
        "description": "GCP project ID prefix (supports {N} or {NN} placeholders).",
    },
    "billing_account_id": {
        "flag": "--billing-account",
        "type": "string",
        "default": "<BILLING_ACCOUNT_ID>",
        "description": "Google Cloud Billing Account ID.",
    },
    "folder_id": {
        "flag": "--folder-id",
        "type": "string",
        "default": "",
        "description": "Optional parent GCP Folder ID.",
    },
    "region": {
        "flag": "--region",
        "type": "string",
        "default": "global",
        "description": "Antigravity client auth region (must be 'global').",
    },
    "compute_region": {
        "flag": "--compute-region",
        "type": "string",
        "default": "us-central1",
        "description": "Default region for Cloud Run workloads.",
    },
    "budget_alert_usd": {
        "flag": "--budget-alert",
        "type": "integer",
        "default": 250,
        "description": "Cloud Billing budget alert threshold per team in USD.",
    },
    "rate_limit_rpm": {
        "flag": "--rate-limit",
        "type": "integer",
        "default": 150,
        "description": "Target rate limit RPM for prediction overrides.",
    },
    "group_email_pattern": {
        "flag": "--group-email-pattern",
        "type": "string",
        "default": "agy-workshop-team{NN}@example.com",
        "description": "Zero-padded team group email pattern ({NN} = 01..05, {N} = 1..5).",
    },
    "enable_cloud_resources": {
        "flag": "--enable-cloud-resources",
        "type": "boolean",
        "default": True,
        "description": "Include Cloud Run / Storage / Artifact Registry / Cloud Build setup.",
    },
    "enable_model_restrictions": {
        "flag": "--enable-model-restrictions",
        "type": "boolean",
        "default": True,
        "description": "Enforce vertexai.allowedModels org policy on team projects.",
    },
    "allowed_models": {
        "flag": "--allowed-models",
        "type": "string",
        "default": ",".join(DEFAULT_ALLOWED_MODELS),
        "description": "Comma-separated list of allowed Vertex AI model resources.",
    },
    "output_filename": {
        "flag": "--output",
        "type": "string",
        "default": "antigravity_setup_guide.md",
        "description": "Output Markdown filename.",
    },
}


def dump_options_metadata() -> dict[str, dict[str, Any]]:
    """Return option metadata dictionary for --dump-options discovery."""
    return OPTION_DESCRIPTIONS
