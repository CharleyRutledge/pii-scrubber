"""Command-line interface: `pii-scrubber scrub <file>` / `pii-scrubber redact <file>`."""

import os
import sys
import tempfile
from pathlib import Path

import click

from .core import scrub_file
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


if __name__ == "__main__":
    sys.exit(main(prog_name="pii-scrubber"))
