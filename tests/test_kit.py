"""Hermetic unit and integration tests for Antigravity Workshop Kit."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from antigravity_workshop_kit.cli import main
from antigravity_workshop_kit.config import (
    WorkshopConfig,
    dump_options_metadata,
)
from antigravity_workshop_kit.exporter import (
    export_markdown_to_pdf,
    render_html_document,
)
from antigravity_workshop_kit.generator import generate_guide, render_guide_text
from antigravity_workshop_kit.tester import (
    check_bash_syntax,
    check_static_rules,
    extract_bash_blocks,
    run_live_gcp_smoke_test,
    validate_guide_file,
)


def test_config_defaults_and_zero_padded_groups() -> None:
    """Verify default WorkshopConfig values and {NN} zero-padded group formatting."""
    cfg = WorkshopConfig()
    cfg.validate()
    assert cfg.organization == "Workshop"
    assert cfg.auth_mode == "vertex_paygo"
    assert cfg.team_count == 5
    assert cfg.region == "global"
    assert cfg.enable_model_restrictions is True
    assert "publishers/google/models/gemini-4-argon:predict" in cfg.allowed_models
    assert "publishers/google/models/gemini-3.8-flash:predict" in cfg.allowed_models
    assert "publishers/anthropic/models/claude-opus-5.5:predict" in cfg.allowed_models
    assert "publishers/anthropic/models/claude-sonnet-5.5:predict" in cfg.allowed_models
    assert cfg.group_email(1) == "agy-workshop-team01@example.com"
    assert cfg.group_email(5) == "agy-workshop-team05@example.com"
    assert cfg.group_email(12) == "agy-workshop-team12@example.com"
    assert cfg.team_projects() == [
        "workshop-team01",
        "workshop-team02",
        "workshop-team03",
        "workshop-team04",
        "workshop-team05",
    ]


def test_config_allowed_models_parsing_and_validation() -> None:
    """Verify comma-separated string parsing and invalid model validation."""
    parsed = WorkshopConfig.from_dict(
        {"allowed_models": "publishers/google/models/gemini-4-argon:predict, publishers/anthropic/models/claude-opus-5.5:predict"}
    )
    assert len(parsed.allowed_models) == 2
    assert parsed.allowed_models[0] == "publishers/google/models/gemini-4-argon:predict"
    assert parsed.allowed_models[1] == "publishers/anthropic/models/claude-opus-5.5:predict"

    with pytest.raises(ValueError, match="Each item in allowed_models must be a non-empty string"):
        WorkshopConfig(allowed_models=[""]).validate()

    with pytest.raises(ValueError, match="allowed_models must be a list"):
        WorkshopConfig(allowed_models=123).validate()  # type: ignore[arg-type]


def test_config_save_and_load_roundtrip(tmp_path: Path) -> None:
    """Verify WorkshopConfig saves and loads cleanly from .workshop-config.json."""
    cfg_file = tmp_path / ".workshop-config.json"
    original = WorkshopConfig(organization="AcmeCorp", team_count=3)
    original.save(cfg_file)
    loaded = WorkshopConfig.load(cfg_file)
    assert loaded.organization == "AcmeCorp"
    assert loaded.team_count == 3


def test_config_load_fallback_to_example_template(tmp_path: Path) -> None:
    """Verify WorkshopConfig.load falls back to workshop-config.example.json if .workshop-config.json is absent."""
    example_file = tmp_path / "workshop-config.example.json"
    example_file.write_text(
        json.dumps({"organization": "ExampleCorp", "team_count": 7}),
        encoding="utf-8",
    )
    with patch("antigravity_workshop_kit.config.DEFAULT_CONFIG_PATH", tmp_path / ".workshop-config.json"):
        loaded = WorkshopConfig.load(tmp_path / ".workshop-config.json")
        assert loaded.organization == "ExampleCorp"
        assert loaded.team_count == 7


def test_config_validation_rejects_invalid_values() -> None:
    """Verify WorkshopConfig.validate() rejects invalid auth_mode, region, or counts."""
    with pytest.raises(ValueError, match="auth_mode"):
        WorkshopConfig(auth_mode="invalid_mode").validate()

    with pytest.raises(ValueError, match="region must be 'global'"):
        WorkshopConfig(region="us-central1").validate()

    with pytest.raises(ValueError, match="team_count"):
        WorkshopConfig(team_count=0).validate()


def test_dump_options_metadata_contains_organization() -> None:
    """Verify --dump-options metadata exposes organization and all core fields."""
    meta = dump_options_metadata()
    assert "organization" in meta
    assert meta["organization"]["flag"] == "--organization"
    assert "auth_mode" in meta
    assert "group_email_pattern" in meta
    assert "allowed_models" in meta
    assert "enable_model_restrictions" in meta


@pytest.mark.parametrize("auth_mode", ["vertex_paygo", "gemini_enterprise"])
@pytest.mark.parametrize("enable_cloud", [True, False])
def test_generate_and_validate_both_modes_pass(
    tmp_path: Path,
    auth_mode: str,
    enable_cloud: bool,
) -> None:
    """Verify generated guides for vertex_paygo and gemini_enterprise pass bash -n and static rules."""
    out_md = tmp_path / f"guide_{auth_mode}_{enable_cloud}.md"
    cfg = WorkshopConfig(
        organization="Acme",
        auth_mode=auth_mode,
        team_count=4,
        project_prefix="acme-team",
        folder_id="987654321" if enable_cloud else "",
        enable_cloud_resources=enable_cloud,
        output_filename=str(out_md),
    )
    generated_path = generate_guide(cfg, output_path=out_md)
    assert generated_path.exists()

    result = validate_guide_file(generated_path, auth_mode=auth_mode)
    assert result.passed, f"Validation failed with errors: {result.all_errors()}"
    assert result.bash_blocks_checked >= 5
    assert result.syntax_errors == []
    assert result.static_violations == []


def test_tester_catches_bash_syntax_error() -> None:
    """Verify check_bash_syntax catches malformed bash snippets via bash -n."""
    bad_snippet = 'for N in {1..5}; do\n  echo "unclosed loop"\n'
    errors = check_bash_syntax([bad_snippet])
    assert len(errors) == 1
    assert "Bash block #1 syntax error" in errors[0]


def test_tester_catches_static_rule_violations() -> None:
    """Verify check_static_rules flags unapproved APIs, missing roles, and missing flags."""
    bad_markdown = (
        "# Setup Guide\n"
        "Enable unapproved.googleapis.com in region us-central1.\n"
        "```bash\n"
        "gcloud auth login\n"
        "```\n"
    )
    snippets = extract_bash_blocks(bad_markdown)
    violations = check_static_rules(bad_markdown, snippets, auth_mode="vertex_paygo")

    assert any("unapproved.googleapis.com" in v for v in violations)
    assert any("Global" in v for v in violations)
    assert any("gcloud auth login --update-adc" in v for v in violations)
    assert any("roles/aiplatform.user" in v for v in violations)
    assert any("roles/serviceusage.serviceUsageConsumer" in v for v in violations)


def test_live_gcp_smoke_test_mocked() -> None:
    """Verify run_live_gcp_smoke_test checks project reachability and enabled APIs."""
    with patch("antigravity_workshop_kit.tester.subprocess.run") as mock_run:
        mock_run.side_effect = [
             subprocess.CompletedProcess(args=[], returncode=0, stdout="acme-team1\n", stderr=""),
             subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="aiplatform.googleapis.com\nserviceusage.googleapis.com\ncloudaicompanion.googleapis.com\n",
                stderr="",
            ),
        ]
        errors = run_live_gcp_smoke_test("acme-team1", auth_mode="vertex_paygo")
        assert errors == []

    with patch("antigravity_workshop_kit.tester.subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="acme-team1\n", stderr=""),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="serviceusage.googleapis.com\n",
                stderr="",
            ),
        ]
        errors = run_live_gcp_smoke_test("acme-team1", auth_mode="vertex_paygo")
        assert len(errors) == 1
        assert "aiplatform.googleapis.com" in errors[0]


def test_exporter_renders_html_and_invokes_chrome(tmp_path: Path) -> None:
    """Verify HTML rendering and PDF exporter Chrome invocation."""
    cfg = WorkshopConfig(organization="Acme")
    md_text = render_guide_text(cfg)
    html_doc = render_html_document(md_text, title="Test Guide")
    assert "<!DOCTYPE html>" in html_doc
    assert "<table>" in html_doc
    assert "Acme Antigravity Workshop" in html_doc

    md_path = tmp_path / "guide.md"
    pdf_path = tmp_path / "guide.pdf"
    md_path.write_text(md_text, encoding="utf-8")

    def fake_chrome_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        for arg in cmd:
            if arg.startswith("--print-to-pdf="):
                out_file = Path(arg.split("=", 1)[1])
                out_file.write_bytes(b"%PDF-1.4 mock pdf")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("antigravity_workshop_kit.exporter.subprocess.run", side_effect=fake_chrome_run):
        result_pdf = export_markdown_to_pdf(md_path, pdf_path=pdf_path, chrome_binary="/usr/bin/google-chrome")
        assert result_pdf == pdf_path.resolve()
        assert result_pdf.exists()


def test_cli_end_to_end_subcommands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify CLI subcommands: configure --dump-options, configure, generate, test, and run-all."""
    cfg_path = tmp_path / ".workshop-config.json"
    md_path = tmp_path / "out_guide.md"
    pdf_path = tmp_path / "out_guide.pdf"

    # 1. configure --dump-options
    rc = main(["configure", "--dump-options"])
    assert rc == 0
    captured = capsys.readouterr()
    dumped = json.loads(captured.out)
    assert "organization" in dumped

    # 2. configure
    rc = main(
        [
            "configure",
            "--organization=Acme",
            "--auth-mode=gemini_enterprise",
            "--teams=3",
            "--prefix=acme-team",
            f"--output={md_path}",
            f"--config={cfg_path}",
        ]
    )
    assert rc == 0
    saved_cfg = WorkshopConfig.load(cfg_path)
    assert saved_cfg.organization == "Acme"
    assert saved_cfg.auth_mode == "gemini_enterprise"
    assert saved_cfg.team_count == 3

    # 3. generate
    rc = main(["generate", f"--config={cfg_path}"])
    assert rc == 0
    assert md_path.exists()

    # 4. test
    rc = main(["test", f"--config={cfg_path}"])
    assert rc == 0

    # 5. run-all (mocking Chrome subprocess for speed and hermeticity)
    def fake_chrome_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        for arg in cmd:
            if arg.startswith("--print-to-pdf="):
                Path(arg.split("=", 1)[1]).write_bytes(b"%PDF-1.4 mock")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("antigravity_workshop_kit.exporter.subprocess.run", side_effect=fake_chrome_run), patch(
        "antigravity_workshop_kit.exporter.find_chrome_binary", return_value="/usr/bin/google-chrome"
    ):
        rc = main(
            [
                "run-all",
                "--organization=BetaOrg",
                "--auth-mode=vertex_paygo",
                "--teams=5",
                f"--output={md_path}",
                f"--pdf-output={pdf_path}",
                f"--config={cfg_path}",
            ]
        )
        assert rc == 0
        assert pdf_path.exists()
