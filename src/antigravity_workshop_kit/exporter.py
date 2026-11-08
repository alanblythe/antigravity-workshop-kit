"""Headless Chrome PDF compiler for Antigravity Workshop setup guides."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import markdown

BASE_DIR = Path(__file__).resolve().parent
STYLE_PATH = BASE_DIR / "templates" / "print_style.css"

CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def find_chrome_binary() -> str:
    """Locate an installed Chrome/Chromium executable for headless PDF rendering."""
    for candidate in CHROME_CANDIDATES:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        candidate_path = Path(candidate)
        if candidate_path.is_file():
            return str(candidate_path)
    raise FileNotFoundError(
        "Could not locate headless Chrome binary (tried google-chrome, chromium)."
    )


def render_html_document(markdown_text: str, title: str = "Antigravity Workshop Setup Guide") -> str:
    """Convert Markdown text into a print-styled standalone HTML document."""
    css_text = STYLE_PATH.read_text(encoding="utf-8")
    html_body = markdown.markdown(markdown_text, extensions=["tables", "fenced_code"])
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        "<style>\n"
        f"{css_text}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        f"{html_body}\n"
        "</body>\n"
        "</html>\n"
    )


def export_markdown_to_pdf(
    markdown_path: Path,
    pdf_path: Path | None = None,
    chrome_binary: str | None = None,
) -> Path:
    """Compile a Markdown file into a styled PDF using headless Chrome."""
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

    resolved_pdf_path = (pdf_path or markdown_path.with_suffix(".pdf")).resolve()
    resolved_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    markdown_text = markdown_path.read_text(encoding="utf-8")
    html_doc = render_html_document(markdown_text, title=markdown_path.stem)
    chrome_bin = chrome_binary or find_chrome_binary()

    with tempfile.TemporaryDirectory(prefix="agy_workshop_pdf_") as tmp_dir:
        html_path = Path(tmp_dir) / "guide.html"
        html_path.write_text(html_doc, encoding="utf-8")

        cmd = [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            f"--print-to-pdf={resolved_pdf_path}",
            str(html_path),
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0 or not resolved_pdf_path.exists():
            err_detail = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
            raise RuntimeError(f"Headless Chrome PDF export failed: {err_detail}")

    return resolved_pdf_path
