# pii-scrubber

A Python library for scrubbing personally identifiable information (PII) from
documents. Combines regex rules for structured PII (emails, phone numbers,
SSNs, credit cards, IP addresses) with spaCy NER for free-text PII (names,
locations, organizations).

## Install

```bash
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

Optional extras for document formats:

```bash
pip install -e ".[all]"   # pdf + docx + ocr support
```

`ocr` also requires a system Tesseract OCR install (not installable via pip):

```powershell
winget install --id UB-Mannheim.TesseractOCR
```

## Usage

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

Supported file types via `scrub_file`: `.txt`, `.md`, `.pdf`, `.docx`, `.csv`,
`.json`.

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
# and a system Tesseract install (see below) — off by default.
```

| File type | What's preserved |
|---|---|
| `.txt` / `.md` | plain text, redacted in place |
| `.docx` | paragraphs and table cells, PII replaced with `[LABEL]` text |
| `.csv` | rows/columns, redacted per cell |
| `.json` | keys and structure, string values redacted, numbers/bools untouched |
| `.pdf` | original layout and images; PII is truly removed (not just hidden) and covered with a black box, not a `[LABEL]` |

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

### Known limitations

- spaCy's NER model can miss all-caps names or flag unrelated capitalized
  words (e.g. "PAYE", "MyAccount") as ORGANIZATION — regex rules cover the
  common gaps but this isn't perfect for every document layout.
- Without `ocr=True`, PII baked into an image (a photographed ID, a
  screenshot) is not detected — only real text layers are scanned.
- OCR-based image redaction blacks out the *entire* image if any PII is
  found in it, since OCR text can't be reliably mapped back to exact pixel
  coordinates within the image.

## Development

```bash
pytest
```
