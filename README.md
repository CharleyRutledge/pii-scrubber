# pii-scrubber

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/m61v0m5kun)

A Python library for scrubbing personally identifiable information (PII)
from documents **before** you paste or upload them somewhere that isn't
under your control - an LLM chat tool, a support ticket, a shared drive.

**Runs entirely on your machine. No network calls, no telemetry, nothing
uploaded anywhere.** Detection is regex + a local, pretrained spaCy NER
model doing inference only - it does not learn from, retain, or transmit
your documents. You can read exactly what it does: pattern rules live in
[`rules.py`](src/pii_scrubber/rules.py), NER logic in
[`ner.py`](src/pii_scrubber/ner.py).

> **No PII scrubber is complete.** Regex and NER both have real blind
> spots - see [Known limitations](#known-limitations) below, all of which
> came from testing this against real documents. Spot-check the redacted
> output before you rely on it, especially for anything sensitive.

See [docs/USAGE_WALKTHROUGH.md](docs/USAGE_WALKTHROUGH.md) for a step-by-step
CLI walkthrough with a recorded terminal session - generated straight from a
real, passing run of the CLI (`tools/record_demo.py`), so the commands and
output shown are genuine, not hand-written.

## Install

```bash
pip install -e ".[all]"   # pdf + docx + ocr support
python -m spacy download en_core_web_sm
```

Then, from the command line:

```bash
pii-scrubber scrub your_document.pdf
```

For library development (running the test suite, contributing), use the
`dev` extra instead:

```bash
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

`ocr` also requires a system Tesseract OCR install (not installable via pip):

```powershell
winget install --id UB-Mannheim.TesseractOCR
```

## Usage

### Command line

```bash
pii-scrubber scrub document.pdf          # print redacted text + counts
pii-scrubber redact document.pdf         # write document_redacted.pdf
pii-scrubber redact document.pdf --ocr   # also redact PII baked into images
pii-scrubber redact document.pdf -o clean.pdf --no-ner  # regex rules only
```

See [docs/USAGE_WALKTHROUGH.md](docs/USAGE_WALKTHROUGH.md) for a full
recorded walkthrough of these commands against a real file.

### Python API

```python
from pii_scrubber import scrub, scrub_file

result = scrub("Contact Jane Doe at jane.doe@example.com or 555-123-4567.")
print(result.text)
# "Contact [PERSON] at [EMAIL] or [PHONE]."
print(result.counts)
# {"PERSON": 1, "EMAIL": 1, "PHONE": 1}

# Extract + scrub a file directly
result = scrub_file("contract.docx")
```

Supported file types via `scrub_file`: `.txt`, `.md`, `.html`/`.htm`, `.pdf`,
`.docx`, `.csv`, `.json`.

### Format-preserving redaction

`scrub_file` returns flattened plain text. To instead get a redacted copy of
the document in its **original file format**, use `redact_file`:

```python
from pii_scrubber import redact_file

out_path = redact_file("contract.docx")
# writes contract_redacted.docx next to the original, structure intact

redact_file("intake.pdf", output_path="intake_clean.pdf")
# PDF: original layout/images kept, PII burned out with black boxes

redact_file("intake.pdf", ocr=True)
# also OCRs embedded images (scanned IDs, screenshots) and blacks out
# any image whose recognized text contains PII. Requires the `ocr` extra
# and a system Tesseract install (see below) - off by default.
```

| File type | What's preserved |
|---|---|
| `.txt` / `.md` | plain text, redacted in place |
| `.docx` | paragraphs and table cells, PII replaced with `[LABEL]` text |
| `.csv` | rows/columns, redacted per cell |
| `.json` | keys and structure, string values redacted, numbers/bools untouched |
| `.pdf` | original layout and images; PII is truly removed (not just hidden) and covered with a black box, not a `[LABEL]` |
| `.html` / `.htm` | tags/attributes/scripts/styles untouched, only visible text redacted |

### Disabling NER

Regex-only mode skips loading the spaCy model, useful when you only care
about structured identifiers or want to avoid the model dependency:

```python
scrub(text, use_ner=False)
```

### Detected entity types

| Label | Source |
|---|---|
| EMAIL, PHONE, SSN, PPS_NUMBER, CREDIT_CARD, IP_ADDRESS, MAC_ADDRESS, IBAN, EIRCODE, ADDRESS, URL, FILE_PATH, SOCIAL_PROFILE | regex |
| PERSON (also caught via title-prefixed regex, e.g. "MR CHARLEY RUTLEDGE") | regex + spaCy NER |
| LOCATION, ORGANIZATION, AFFILIATION | spaCy NER |

`PPS_NUMBER` is the Irish equivalent of an SSN; `EIRCODE` is the Irish postal
code. `FILE_PATH` catches `file://` URIs, which often leak a local OS
username via the path.

## Known limitations

- **Generic NER on real documents misses things.** spaCy's small English
  model can fail to recognize a name with no surrounding sentence context
  (e.g. a signer's name alone on a line in a letter footer), even when it
  gets the same name right in a full sentence. A structural heuristic
  catches some of these (a short all-caps line next to a detected address
  is treated as a place name), but this isn't exhaustive.
- **Country/format-specific identifiers you haven't added a rule for won't
  be caught.** The regex rules were built out against real US/Irish
  documents during development; a national ID format, postal code, or
  phone format from elsewhere may need its own rule - see
  [CONTRIBUTING.md](CONTRIBUTING.md).
- **Without `ocr=True`, PII baked into an image is invisible to the
  tool** - a photographed ID, a screenshot, a scanned signature. Only
  real text layers are scanned by default.
- **OCR-based image redaction blacks out the entire image**, not just the
  PII within it, since OCR text can't be reliably mapped back to exact
  pixel coordinates inside the image.
- **A PDF's embedded font can occasionally have a broken glyph mapping**,
  causing text extraction to silently drop or mangle a character. The
  tool detects this (`�` replacement characters) and warns you, or -
  with `ocr=True` - falls back to rasterizing and OCR'ing that page
  instead of trusting the broken text layer.

## Development

```bash
pytest
```

Contributions welcome - see [CONTRIBUTING.md](CONTRIBUTING.md). For
reporting a missed detection, see [SECURITY.md](SECURITY.md) (please don't
post real documents or real PII in a public issue).

## License

[MIT](LICENSE)
