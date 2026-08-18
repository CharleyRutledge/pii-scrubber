"""Format-preserving redaction: write a redacted copy of a document in its
original file format, instead of flattened plain text.

.txt/.md  -> redacted text written back out
.docx     -> paragraph/table-cell text replaced in place, structure kept
.csv      -> redacted per-cell, rows/columns kept
.json     -> string values redacted in place, structure/keys kept
.pdf      -> original layout/images kept; black boxes burned over PII text
"""

import csv
import json
from pathlib import Path

from .core import scrub


def redact_file(
    path: str | Path,
    output_path: str | Path | None = None,
    use_ner: bool = True,
    ner_model: str = "en_core_web_sm",
    ner_labels: set[str] | None = None,
) -> Path:
    """Write a redacted copy of `path` in the same file format and return its path.

    If `output_path` is omitted, writes next to the original as
    "<stem>_redacted<suffix>".
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if output_path is None:
        output_path = path.with_name(f"{path.stem}_redacted{path.suffix}")
    output_path = Path(output_path)

    def _scrub(text: str) -> str:
        return scrub(text, use_ner=use_ner, ner_model=ner_model, ner_labels=ner_labels).text

    if suffix in {".txt", ".md"}:
        _redact_plain_text(path, output_path, _scrub)
    elif suffix == ".docx":
        _redact_docx(path, output_path, _scrub)
    elif suffix == ".csv":
        _redact_csv(path, output_path, _scrub)
    elif suffix == ".json":
        _redact_json(path, output_path, _scrub)
    elif suffix == ".pdf":
        _redact_pdf(path, output_path, use_ner, ner_model, ner_labels)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    return output_path


def _redact_plain_text(path: Path, output_path: Path, scrub_fn) -> None:
    text = path.read_text(encoding="utf-8")
    output_path.write_text(scrub_fn(text), encoding="utf-8")


def _set_paragraph_text(paragraph, new_text: str) -> None:
    """Replace a python-docx paragraph's visible text with `new_text`,
    collapsing all runs into one (per-run formatting is not preserved
    since a PII span can straddle multiple runs).
    """
    if not paragraph.runs:
        return
    paragraph.runs[0].text = new_text
    for run in paragraph.runs[1:]:
        run.text = ""


def _redact_docx(path: Path, output_path: Path, scrub_fn) -> None:
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError(
            "DOCX support requires python-docx. Install with: pip install pii-scrubber[docx]"
        ) from exc

    document = docx.Document(str(path))

    for paragraph in document.paragraphs:
        if paragraph.text:
            _set_paragraph_text(paragraph, scrub_fn(paragraph.text))

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    if paragraph.text:
                        _set_paragraph_text(paragraph, scrub_fn(paragraph.text))

    document.save(str(output_path))


def _redact_csv(path: Path, output_path: Path, scrub_fn) -> None:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    redacted_rows = [[scrub_fn(cell) for cell in row] for row in rows]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(redacted_rows)


def _redact_json(path: Path, output_path: Path, scrub_fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))

    def walk(value):
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, str):
            return scrub_fn(value)
        return value

    redacted = walk(data)
    output_path.write_text(json.dumps(redacted, indent=2), encoding="utf-8")


def _redact_pdf(
    path: Path,
    output_path: Path,
    use_ner: bool,
    ner_model: str,
    ner_labels: set[str] | None,
) -> None:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires PyMuPDF. Install with: pip install pii-scrubber[pdf]"
        ) from exc

    with fitz.open(str(path)) as doc:
        for page in doc:
            page_text = page.get_text()
            if not page_text.strip():
                continue

            result = scrub(
                page_text, use_ner=use_ner, ner_model=ner_model, ner_labels=ner_labels
            )
            pii_strings = {e.text for e in result.entities if e.text.strip()}

            for pii_text in pii_strings:
                for rect in page.search_for(pii_text):
                    page.add_redact_annot(rect, fill=(0, 0, 0))

            page.apply_redactions()

        doc.save(str(output_path))
