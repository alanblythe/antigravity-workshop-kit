"""Jinja2 template rendering engine for Antigravity Workshop setup guides."""

from __future__ import annotations

from pathlib import Path
import jinja2

from antigravity_workshop_kit.config import WorkshopConfig

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
DEFAULT_TEMPLATE_NAME = "setup_guide.md.j2"


def render_guide_text(
    config: WorkshopConfig,
    template_name: str = DEFAULT_TEMPLATE_NAME,
) -> str:
    """Render the setup guide Markdown string from a validated WorkshopConfig."""
    config.validate()
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_name)
    return template.render(
        config=config,
        team_projects=config.team_projects(),
        project_placeholder=config.project_id_placeholder(),
        first_project_id=config.project_id(1),
        last_project_id=config.project_id(config.team_count),
        bash_project_id=config.bash_project_id_expr(),
        bash_group_email=config.bash_group_email_expr(),
        first_group_email=config.group_email(1),
        last_group_email=config.group_email(config.team_count),
        email_domain=config.email_domain(),
    )


def generate_guide(
    config: WorkshopConfig,
    output_path: Path | None = None,
) -> Path:
    """Render the setup guide and write it to output_path (or config.output_filename)."""
    target_path = output_path or Path(config.output_filename)
    rendered = render_guide_text(config)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(rendered, encoding="utf-8")
    return target_path
