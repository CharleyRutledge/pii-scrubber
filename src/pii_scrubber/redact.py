"""Format-preserving redaction: write a redacted copy of a document in its
original file format, instead of flattened plain text.

.txt/.md  -> redacted text written back out
.docx     -> paragraph/table-cell text replaced in place, structure kept
.csv      -> redacted per-cell, rows/columns kept
.json     -> string values redacted in place, structure/keys kept
.pdf      -> original layout/images kept; black boxes burned over PII text
.html/.htm -> tags/attributes kept, only visible text nodes redacted
"""

import csv
import json
from pathlib import Path

from .core import scrub
from .html_tools import split_html_segments


def redact_file(
    path: str | Path,
    output_path: str | Path | None = None,
    use_ner: bool = True,
    ner_model: str = "en_core_web_sm",
    ner_labels: set[str] | None = None,
    ocr: bool = False,
) -> Path:
    """Write a redacted copy of `path` in the same file format and return its path.

    If `output_path` is omitted, writes next to the original as
    "<stem>_redacted<suffix>".

    `ocr` (PDF only) additionally OCRs embedded images and fully blacks out
    any image whose recognized text contains PII (e.g. a photographed ID or
    a screenshot). Requires the `ocr` extra and a system Tesseract install —
    see `pii_scrubber.ocr` for setup. Off by default since it's slower and
    pulls in an extra system dependency.
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
    elif suffix in {".html", ".htm"}:
        _redact_html(path, output_path, _scrub)
    elif suffix == ".docx":
        _redact_docx(path, output_path, _scrub)
    elif suffix == ".csv":
        _redact_csv(path, output_path, _scrub)
    elif suffix == ".json":
        _redact_json(path, output_path, _scrub)
    elif suffix == ".pdf":
        _redact_pdf(path, output_path, use_ner, ner_model, ner_labels, ocr)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    return output_path


def _redact_plain_text(path: Path, output_path: Path, scrub_fn) -> None:
    text = path.read_text(encoding="utf-8")
    output_path.write_text(scrub_fn(text), encoding="utf-8")


def _redact_html(path: Path, output_path: Path, scrub_fn) -> None:
    html = path.read_text(encoding="utf-8")
    segments = split_html_segments(html)
    rebuilt = "".join(
        seg if is_tag_or_skipped else scrub_fn(seg) for is_tag_or_skipped, seg in segments
    )
    output_path.write_text(rebuilt, encoding="utf-8")


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
    ocr: bool,
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
            if page_text.strip():
                result = scrub(
                    page_text, use_ner=use_ner, ner_model=ner_model, ner_labels=ner_labels
                )
                pii_strings = {e.text for e in result.entities if e.text.strip()}

                for pii_text in pii_strings:
                    for rect in page.search_for(pii_text):
                        page.add_redact_annot(rect, fill=(0, 0, 0))

            if ocr:
                _redact_page_images(doc, page, fitz, use_ner, ner_model, ner_labels)

            page.apply_redactions()

        doc.save(str(output_path))


def _redact_page_images(doc, page, fitz, use_ner, ner_model, ner_labels) -> None:
    """OCR each image on the page; if any PII is found in it, black out the
    whole image region. We can't reliably map OCR'd text back to pixel
    coordinates within the image, so this over-redacts (whole image, not
    just the PII substring) rather than risk leaving PII visible.
    """
    from .ocr import ocr_image_bytes

    for img in page.get_images(full=True):
        xref = img[0]
        try:
            image_bytes = doc.extract_image(xref)["image"]
            ocr_text = ocr_image_bytes(image_bytes)
        except Exception:
            continue

        if not ocr_text.strip():
            continue

        result = scrub(ocr_text, use_ner=use_ner, ner_model=ner_model, ner_labels=ner_labels)
        if not result.entities:
            continue

        for rect in page.get_image_rects(xref):
            page.add_redact_annot(rect, fill=(0, 0, 0))
