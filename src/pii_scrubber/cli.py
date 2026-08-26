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
from .workspace import OUTPUTS_DIR, UPLOADS_DIR, import_file, list_workspace_files, output_path_for


@click.group(invoke_without_command=True)
@click.version_option(package_name="pii-scrubber")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Scrub PII from documents, locally, before you paste/upload them elsewhere.

    Run with no command for an interactive menu.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(menu)


def _run_scrub(path: str, no_ner: bool, output: str | None, open_after: bool) -> None:
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
@click.option("--no-ner", is_flag=True, help="Skip spaCy NER, regex rules only.")
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None,
              help="Also write the redacted text to this file (scrub always prints to stdout too).")
@click.option("--open", "open_after", is_flag=True,
              help="Open the redacted text (written to --output, or a temp file if "
                   "--output wasn't given), prompting you to choose which app to "
                   "open it with (Windows) or the OS default app (macOS/Linux).")
def scrub(path: str, no_ner: bool, output: str | None, open_after: bool) -> None:
    """Print PII-redacted text extracted from PATH, plus a summary count."""
    _run_scrub(path, no_ner, output, open_after)


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", type=click.Path(dir_okay=False), default=None,
              help="Output path (default: <name>_redacted<ext> next to the original).")
@click.option("--no-ner", is_flag=True, help="Skip spaCy NER, regex rules only.")
@click.option("--ocr", is_flag=True,
              help="Also OCR embedded PDF images and black out any that contain PII "
                   "(requires the `ocr` extra + a system Tesseract install).")
@click.option("--open", "open_after", is_flag=True,
              help="Once written, prompt you to choose which app to open the "
                   "redacted file with (Windows) or the OS default app (macOS/Linux).")
def redact(path: str, output: str | None, no_ner: bool, ocr: bool, open_after: bool) -> None:
    """Write a redacted copy of PATH in its original file format."""
    out_path = redact_file(path, output_path=output, use_ner=not no_ner, ocr=ocr, open_after=open_after)
    click.echo(f"Wrote {out_path}")


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
def upload(path: str) -> None:
    """Copy PATH into pii-scrubber's local, offline file storage
    (~/.pii-scrubber/uploads) so it shows up in `pii-scrubber menu` / `list`.
    """
    dest = import_file(path)
    click.echo(f"Uploaded to {dest}")


@main.command(name="list")
def list_files() -> None:
    """List files stored locally by pii-scrubber (uploads and outputs)."""
    uploads, outputs = list_workspace_files()

    click.echo(f"Uploads ({UPLOADS_DIR}):")
    if uploads:
        for p in uploads:
            click.echo(f"  {p.name}")
    else:
        click.echo("  (none)")

    click.echo(f"\nOutputs ({OUTPUTS_DIR}):")
    if outputs:
        for p in outputs:
            click.echo(f"  {p.name}")
    else:
        click.echo("  (none)")


def _menu_pick_path(uploads: list) -> Path:
    if uploads:
        click.echo("\nUploaded files:")
        for i, p in enumerate(uploads, 1):
            click.echo(f"  {i}) {p.name}")
        click.echo("  ...or paste/type a full path to any other file.")
    raw = click.prompt("File").strip().strip('"')
    if raw.isdigit() and uploads and 1 <= int(raw) <= len(uploads):
        return uploads[int(raw) - 1]
    return Path(raw)


def _menu_upload() -> None:
    raw = click.prompt("Path to the file you want to upload").strip().strip('"')
    dest = import_file(raw)
    click.echo(f"Uploaded to {dest}")


def _menu_scrub() -> None:
    uploads, _ = list_workspace_files()
    path = _menu_pick_path(uploads)
    if not path.exists():
        click.echo(f"No such file: {path}", err=True)
        return

    no_ner = not click.confirm("Use spaCy NER (name/location/organization detection)?", default=True)
    save = click.confirm("Save the scrubbed text to a local file?", default=True)
    open_after = save and click.confirm("Open it once saved?", default=False)

    output = str(output_path_for(path, "scrubbed", ".txt")) if save else None
    _run_scrub(str(path), no_ner, output, open_after)


def _menu_redact() -> None:
    uploads, _ = list_workspace_files()
    path = _menu_pick_path(uploads)
    if not path.exists():
        click.echo(f"No such file: {path}", err=True)
        return

    no_ner = not click.confirm("Use spaCy NER (name/location/organization detection)?", default=True)
    ocr = path.suffix.lower() == ".pdf" and click.confirm(
        "Also OCR embedded images (requires Tesseract)?", default=False
    )
    open_after = click.confirm("Open the redacted copy once saved?", default=False)

    output = output_path_for(path, "redacted")
    out_path = redact_file(path, output_path=output, use_ner=not no_ner, ocr=ocr, open_after=open_after)
    click.echo(f"Wrote {out_path}")


@main.command()
@click.pass_context
def menu(ctx: click.Context) -> None:
    """Interactive "PII - Scrubber" menu - pick an action instead of
    remembering command-line flags.
    """
    click.echo("=" * 32)
    click.echo("      PII - Scrubber")
    click.echo("=" * 32)

    while True:
        click.echo(
            "\n1) Upload a file\n"
            "2) Scrub a file (print redacted text)\n"
            "3) Redact a file (save a cleaned copy)\n"
            "4) List stored files\n"
            "5) Doctor (check NER availability)\n"
            "0) Exit"
        )
        choice = click.prompt("Choose an option", type=click.Choice(["0", "1", "2", "3", "4", "5"]))

        if choice == "0":
            break
        elif choice == "1":
            _menu_upload()
        elif choice == "2":
            _menu_scrub()
        elif choice == "3":
            _menu_redact()
        elif choice == "4":
            ctx.invoke(list_files)
        elif choice == "5":
            ctx.invoke(doctor)


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
