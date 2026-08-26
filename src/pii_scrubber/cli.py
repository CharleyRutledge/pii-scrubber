"""Command-line interface: `pii-scrubber scrub <file>` / `pii-scrubber redact <file>`."""

import os
import sys
import tempfile
from pathlib import Path

import click

from .core import scrub_file
from .diagnostics import (
    check_ner_available,
    open_code_integrity_event_log,
    open_smart_app_control_settings,
)
from .open_file import open_with_default_app
from .redact import redact_file


@click.group()
@click.version_option(package_name="pii-scrubber")
def main() -> None:
    """Scrub PII from documents, locally, before you paste/upload them elsewhere."""


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--no-ner", is_flag=True, help="Skip spaCy NER, regex rules only.")
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None,
              help="Also write the redacted text to this file (scrub always prints to stdout too).")
@click.option("--open", "open_after", is_flag=True,
              help="Open the redacted text in its default app (written to --output, "
                   "or a temp file if --output wasn't given).")
def scrub(path: str, no_ner: bool, output: str | None, open_after: bool) -> None:
    """Print PII-redacted text extracted from PATH, plus a summary count."""
    result = scrub_file(path, use_ner=not no_ner)
    click.echo(result.text)
    click.echo("", err=True)
    if result.counts:
        click.echo("Found:", err=True)
        for label, count in sorted(result.counts.items()):
            click.echo(f"  {label}: {count}", err=True)
    else:
        click.echo("No PII detected.", err=True)

    out_path: Path | None = None
    if output:
        out_path = Path(output)
    elif open_after:
        fd, name = tempfile.mkstemp(suffix=".txt", prefix="pii-scrubber-")
        os.close(fd)  # close the raw descriptor before reopening via write_text
        out_path = Path(name)

    if out_path is not None:
        out_path.write_text(result.text, encoding="utf-8")

    if open_after and out_path is not None:
        open_with_default_app(out_path)


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None,
              help="Output path (default: <name>_redacted<ext> next to the original).")
@click.option("--no-ner", is_flag=True, help="Skip spaCy NER, regex rules only.")
@click.option("--ocr", is_flag=True,
              help="Also OCR embedded PDF images and black out any that contain PII "
                   "(requires the `ocr` extra + a system Tesseract install).")
@click.option("--open", "open_after", is_flag=True,
              help="Open the redacted file in its default app once it's written.")
def redact(path: str, output: str | None, no_ner: bool, ocr: bool, open_after: bool) -> None:
    """Write a redacted copy of PATH in its original file format."""
    out_path = redact_file(path, output_path=output, use_ner=not no_ner, ocr=ocr, open_after=open_after)
    click.echo(f"Wrote {out_path}")


@main.command()
def doctor() -> None:
    """Check whether spaCy NER can actually load in this environment.

    If it's blocked by a Windows Application Control / Smart App Control
    policy (ImportError: DLL load failed... "An Application Control policy
    has blocked this file"), offers to jump straight to the relevant
    Windows settings, rather than making you find them yourself.
    """
    click.echo("Checking spaCy NER availability...")
    result = check_ner_available()

    if result.ok:
        click.echo("OK: " + result.detail)
        return

    click.echo("NOT OK: " + result.detail, err=True)

    if not result.blocked_by_app_control:
        click.echo(
            "\nThis doesn't look like a policy block - looks like a missing "
            "install/model instead. Try:\n"
            "  pip install -e \".[dev]\"\n"
            "  python -m spacy download en_core_web_sm",
            err=True,
        )
        click.echo(
            "\nIn the meantime, --no-ner still works for every rule that "
            "doesn't rely on spaCy (email, phone, national IDs, etc.).",
        )
        return

    click.echo(
        "\nThis is a Windows Application Control policy blocking spaCy's "
        "compiled (unsigned) code from loading - either Smart App Control "
        "or an org-managed WDAC policy, not a bug in pii-scrubber.\n"
        "\n--no-ner sidesteps it entirely (skips spaCy, regex rules still run).",
    )

    if sys.platform != "win32":
        return

    if click.confirm(
        "\nOpen Windows Security's Smart App Control settings page now?",
        default=True,
    ):
        open_smart_app_control_settings()
        click.echo(
            "Opened. If it says \"On\", Microsoft only lets you turn it off "
            "via a full Windows reinstall. If it says \"Evaluation\", you can "
            "turn it off right there. If it's already \"Off\", this is a "
            "WDAC/org policy instead - see the event log option below.",
        )

    if click.confirm(
        "Open Event Viewer at the CodeIntegrity log (shows the exact policy "
        "+ file hash that was blocked)?",
        default=False,
    ):
        open_code_integrity_event_log()


if __name__ == "__main__":
    sys.exit(main(prog_name="pii-scrubber"))
