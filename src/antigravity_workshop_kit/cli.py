"""CLI entrypoint for Antigravity Workshop Kit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from antigravity_workshop_kit.config import (
    DEFAULT_CONFIG_PATH,
    VALID_AUTH_MODES,
    WorkshopConfig,
    dump_options_metadata,
)
from antigravity_workshop_kit.exporter import export_markdown_to_pdf
from antigravity_workshop_kit.generator import generate_guide
from antigravity_workshop_kit.tester import validate_guide_file


def _add_config_override_flags(parser: argparse.ArgumentParser) -> None:
    """Attach common workshop configuration flags to a subcommand parser."""
    parser.add_argument(
        "--organization",
        dest="organization",
        help="Organization name (e.g. 'Acme').",
    )
    parser.add_argument(
        "--auth-mode",
        choices=VALID_AUTH_MODES,
        help="Licensing/auth model ('vertex_paygo' or 'gemini_enterprise').",
    )
    parser.add_argument(
        "--teams",
        type=int,
        dest="team_count",
        help="Number of team projects to provision.",
    )
    parser.add_argument(
        "--prefix",
        dest="project_prefix",
        help="GCP project ID prefix.",
    )
    parser.add_argument(
        "--billing-account",
        dest="billing_account_id",
        help="Google Cloud Billing Account ID.",
    )
    parser.add_argument(
        "--folder-id",
        dest="folder_id",
        help="Optional parent GCP Folder ID.",
    )
    parser.add_argument(
        "--region",
        dest="region",
        help="Antigravity client auth region (must be 'global').",
    )
    parser.add_argument(
        "--compute-region",
        dest="compute_region",
        help="Default region for Cloud Run workloads.",
    )
    parser.add_argument(
        "--budget-alert",
        type=int,
        dest="budget_alert_usd",
        help="Cloud Billing budget alert threshold per team in USD.",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        dest="rate_limit_rpm",
        help="Target rate limit RPM for prediction overrides.",
    )
    parser.add_argument(
        "--group-email-pattern",
        dest="group_email_pattern",
        help="Zero-padded team group email pattern (e.g. 'agy-workshop-team{NN}@example.com').",
    )
    cloud_group = parser.add_mutually_exclusive_group()
    cloud_group.add_argument(
        "--enable-cloud-resources",
        dest="enable_cloud_resources",
        action="store_true",
        default=None,
        help="Include Cloud Run / Storage / Artifact Registry setup (default: true).",
    )
    cloud_group.add_argument(
        "--no-cloud-resources",
        dest="enable_cloud_resources",
        action="store_false",
        default=None,
        help="Inference-only setup without Cloud Run / Storage / Artifact Registry.",
    )
    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument(
        "--enable-model-restrictions",
        dest="enable_model_restrictions",
        action="store_true",
        default=None,
        help="Enforce vertexai.allowedModels org policy on team projects (default: true).",
    )
    model_group.add_argument(
        "--no-model-restrictions",
        dest="enable_model_restrictions",
        action="store_false",
        default=None,
        help="Allow all Vertex AI foundation models without org policy restriction.",
    )
    parser.add_argument(
        "--allowed-models",
        dest="allowed_models",
        help="Comma-separated list of allowed Vertex AI model resources.",
    )
    parser.add_argument(
        "--output",
        dest="output_filename",
        help="Output Markdown filename.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to .workshop-config.json state file.",
    )


def _apply_cli_overrides(config: WorkshopConfig, args: argparse.Namespace) -> WorkshopConfig:
    """Merge non-None CLI flag overrides onto an existing WorkshopConfig instance."""
    data = config.to_dict()
    for field_name in data:
        if hasattr(args, field_name):
            val = getattr(args, field_name)
            if val is not None:
                data[field_name] = val
    return WorkshopConfig.from_dict(data)


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level CLI ArgumentParser and subcommands."""
    parser = argparse.ArgumentParser(
        prog="antigravity-workshop-kit",
        description=(
            "Generate, validate, and export customized Google Cloud setup guides "
            "for Antigravity workshops."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. configure
    cfg_parser = subparsers.add_parser(
        "configure",
        help="Initialize or update .workshop-config.json (or inspect options via --dump-options).",
    )
    cfg_parser.add_argument(
        "--dump-options",
        action="store_true",
        help="Print JSON metadata describing all configurable workshop parameters.",
    )
    _add_config_override_flags(cfg_parser)

    # 2. generate
    gen_parser = subparsers.add_parser(
        "generate",
        help="Render the Markdown workshop setup guide from configuration.",
    )
    _add_config_override_flags(gen_parser)

    # 3. test
    test_parser = subparsers.add_parser(
        "test",
        help="Extract bash blocks and validate syntax (bash -n) and static best-practice rules.",
    )
    test_parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Markdown file to test (defaults to output_filename in .workshop-config.json).",
    )
    test_parser.add_argument(
        "--auth-mode",
        choices=VALID_AUTH_MODES,
        default=None,
        help="Override auth_mode for static rule assertions.",
    )
    test_parser.add_argument(
        "--live-project",
        default=None,
        help="Optional live GCP project ID to smoke test via gcloud.",
    )
    test_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to .workshop-config.json state file.",
    )

    # 4. export-pdf
    pdf_parser = subparsers.add_parser(
        "export-pdf",
        help="Compile the generated Markdown guide into a styled PDF via headless Chrome.",
    )
    pdf_parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input Markdown file (defaults to output_filename in .workshop-config.json).",
    )
    pdf_parser.add_argument(
        "--pdf-output",
        type=Path,
        default=None,
        help="Output PDF path (defaults to <input_stem>.pdf).",
    )
    pdf_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to .workshop-config.json state file.",
    )

    # 5. run-all
    all_parser = subparsers.add_parser(
        "run-all",
        help="Run configure -> generate -> test -> export-pdf sequentially (fail-fast).",
    )
    _add_config_override_flags(all_parser)
    all_parser.add_argument(
        "--live-project",
        default=None,
        help="Optional live GCP project ID to smoke test during the test stage.",
    )
    all_parser.add_argument(
        "--pdf-output",
        type=Path,
        default=None,
        help="Optional output PDF path.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI command and return an exit status code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "configure":
            if args.dump_options:
                print(json.dumps(dump_options_metadata(), indent=2))
                return 0
            base_cfg = WorkshopConfig.load(args.config)
            updated_cfg = _apply_cli_overrides(base_cfg, args)
            saved_path = updated_cfg.save(args.config)
            print(f"[configure] Saved workshop configuration to {saved_path}")
            return 0

        if args.command == "generate":
            base_cfg = WorkshopConfig.load(args.config)
            effective_cfg = _apply_cli_overrides(base_cfg, args)
            out_path = generate_guide(effective_cfg)
            print(f"[generate] Rendered setup guide to {out_path}")
            return 0

        if args.command == "test":
            base_cfg = WorkshopConfig.load(args.config)
            guide_path = args.input or Path(base_cfg.output_filename)
            auth_mode = args.auth_mode or base_cfg.auth_mode
            result = validate_guide_file(
                guide_path=guide_path,
                auth_mode=auth_mode,
                live_project=args.live_project,
            )
            if not result.passed:
                print(
                    f"[test] FAILED ({len(result.all_errors())} error(s) in {guide_path}):",
                    file=sys.stderr,
                )
                for err in result.all_errors():
                    print(f"  - {err}", file=sys.stderr)
                return 1
            print(
                f"[test] PASSED ({result.bash_blocks_checked} bash blocks validated, 0 static rule violations in {guide_path})"
            )
            return 0

        if args.command == "export-pdf":
            base_cfg = WorkshopConfig.load(args.config)
            md_path = args.input or Path(base_cfg.output_filename)
            pdf_path = export_markdown_to_pdf(md_path, pdf_path=args.pdf_output)
            print(f"[export-pdf] Compiled PDF to {pdf_path}")
            return 0

        if args.command == "run-all":
            base_cfg = WorkshopConfig.load(args.config)
            updated_cfg = _apply_cli_overrides(base_cfg, args)
            saved_cfg_path = updated_cfg.save(args.config)
            print(f"[1/4 configure] Saved configuration to {saved_cfg_path}")

            md_path = generate_guide(updated_cfg)
            print(f"[2/4 generate] Rendered setup guide to {md_path}")

            result = validate_guide_file(
                guide_path=md_path,
                auth_mode=updated_cfg.auth_mode,
                live_project=args.live_project,
            )
            if not result.passed:
                print(
                    f"[3/4 test] FAILED ({len(result.all_errors())} error(s)):",
                    file=sys.stderr,
                )
                for err in result.all_errors():
                    print(f"  - {err}", file=sys.stderr)
                return 1
            print(
                f"[3/4 test] PASSED ({result.bash_blocks_checked} bash blocks validated, 0 static violations)"
            )

            pdf_path = export_markdown_to_pdf(md_path, pdf_path=args.pdf_output)
            print(f"[4/4 export-pdf] Compiled PDF to {pdf_path}")
            return 0

    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
