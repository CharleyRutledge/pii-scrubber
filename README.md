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
output shown are genuine, not hand-written. See
[CHANGELOG.md](CHANGELOG.md) for a full status report of what's covered
(document formats, languages tested, all 39 national ID formats, passport/
health-insurance detection) and what's explicitly not implemented yet.

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
pii-scrubber redact document.pdf --open  # open the redacted file when done
pii-scrubber scrub document.pdf --open   # write scrubbed text to a temp file and open it
pii-scrubber scrub document.pdf -o clean.txt --open  # ...or to a chosen path
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

redact_file("intake.pdf", open_after=True)
# launches the redacted file in its default app once written, so you can
# immediately eyeball the result - off by default (surprising behavior for
# anything running unattended: scripts, CI, batch jobs).
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
| EMAIL, PHONE, SSN, CREDIT_CARD, IP_ADDRESS, MAC_ADDRESS, IBAN, ADDRESS, URL, FILE_PATH, SOCIAL_PROFILE | regex |
| National IDs (39 countries, see table below) | regex, checksum-validated where a real algorithm exists |
| `PASSPORT_MRZ` (any issuing country) | regex, ICAO 9303 checksum-validated |
| Health insurance: `DE_KVNR` (Germany), `UK_NHS_NUMBER`, `CA_ON_HEALTH` (Ontario) | regex, checksum-validated |
| PERSON (also caught via title-prefixed regex, e.g. "MR CHARLEY RUTLEDGE") | regex + spaCy NER |
| LOCATION, ORGANIZATION, AFFILIATION | spaCy NER |

`FILE_PATH` catches `file://` URIs, which often leak a local OS username via
the path. `PASSPORT_MRZ` detects the two-line Machine Readable Zone printed
on every passport worldwide (ICAO 9303 standard) rather than a per-country
passport-number pattern - passport formats vary hugely by country and
mostly have no public checksum of their own, so a bare "letters + digits"
pattern would be far too collision-prone; the MRZ is identical in structure
across every issuing country and carries four real check digits. Verified
against ICAO's own published worked example - see `tests/test_mrz.py`.

**Driver's licences are deliberately not implemented.** Researched the UK
format specifically (the most well-documented one): it deterministically
encodes surname, birth date, and initials into 11 of its 16 characters,
but its own documentation describes the final characters as
"computer-generated"/random - there is no real checksum. US licences vary
by state with no federal standard and, as far as could be verified, no
checksum either. Implementing a format-only pattern for either would
reintroduce exactly the collision risk that `_US_PASSPORT` (removed
earlier - see git history) had: matching against ordinary alphanumeric
codes throughout a document. If you know of a driver's licence format
with a real public checksum, contributions are welcome.

#### National ID coverage

| Country | Label | Checksum algorithm |
|---|---|---|
| Ireland | `PPS_NUMBER` | letter checksum |
| Ireland (postal code) | `EIRCODE` | format only |
| United Kingdom | `UK_NINO` | format only (letter/prefix constraints) |
| United States | `SSN` | format only |
| France | `FR_INSEE` | mod 97 |
| Germany | `DE_RVNR` | weighted digit-sum |
| Spain | `ES_NIF` / `ES_NIE` | mod 23 letter lookup |
| Italy | `IT_CODICE_FISCALE` | position-weighted mod 26 |
| Netherlands | `NL_BSN` | elfproef (mod 11) |
| Poland | `PL_PESEL` | weighted mod 10 |
| Sweden | `SE_PERSONNUMMER` | Luhn |
| Norway | `NO_FODSELSNUMMER` | two-stage mod 11 |
| Portugal | `PT_NIF` | weighted mod 11 |
| Russia | `RU_INN` | two-stage weighted mod 11 |
| Turkey | `TR_TCKN` | weighted mod 10 |
| Romania | `RO_CNP` | weighted mod 11 |
| Hungary | `HU_SZEMELYI` | weighted mod 11 (direction depends on birth year) |
| Brazil | `BR_CPF` | two-stage weighted mod 11 |
| Canada | `CA_SIN` | Luhn |
| China | `CN_RESIDENT_ID` | ISO 7064 MOD 11-2 |
| South Korea | `KR_RRN` | weighted mod 11 |
| Australia | `AU_TFN` | weighted mod 11 |
| Algeria | `DZ_NIN` | modified Luhn |
| Austria | `AT_SVNR` | weighted mod 11 |
| Greece | `EL_AMKA` | Luhn |
| Mexico | `MX_IMSS` | digital-root weighted sum |
| Estonia | `EE_ISIKUKOOD` | two-scale mod 11 |
| Finland | `FI_HETU` | mod 31 letter lookup |
| Switzerland | `CH_AHV` | EAN-13-style checksum, fixed `756` prefix |
| Israel | `IL_TZ` | Luhn-family |
| Croatia | `HR_OIB` | ISO 7064 MOD 11,10 |
| Latvia | `LV_PERSONAS_KODS` | weighted mod 11 |
| North Macedonia | `MK_EMBG` | weighted mod 11 |
| Belgium | `BE_RRN` | mod 97 |
| Bosnia and Herzegovina | `BA_JMB` | weighted mod 11 (see note below) |
| Ukraine | `UA_RNOKPP` | weighted mod 11 mod 10 |
| Taiwan | `TW_ID` | letter-weighted positional sum |
| India | `IN_AADHAAR` | Luhn |
| Chile | `CL_RUT` | mod 11, cycling weights |
| Czech Republic / Slovakia | `CZ_SK_RODNE_CISLO` | divisible by 11 |

North Macedonia and Bosnia's formats both descend from the shared
former-Yugoslav JMBG numbering system and use the same weights, but their
reference algorithms differ in one edge case (weighted sum mod 11 == 1):
North Macedonia maps it to check digit 0, Bosnia treats it as genuinely
unallocatable. They're implemented as two separate checked functions, not
one shared one - an earlier version of this code wrongly assumed they were
identical, which silently rejected about 1 in 11 otherwise-valid North
Macedonian numbers (see `tests/test_national_ids.py` for the vector that
catches a regression).

All 39 were validated against hundreds of locale-appropriate synthetic
documents generated with [Faker](https://faker.readthedocs.io/) - see
`tools/audit_national_ids.py`. Where Faker itself can't generate a real
checksum-valid example for a country (it has gaps too - see the script's
output for specifics), the rule is instead verified with a hand-computed
test vector in `tests/test_national_ids.py`. More countries are welcome -
see [CONTRIBUTING.md](CONTRIBUTING.md).

Several of these are also commonly displayed with punctuation/spacing
rather than as a bare digit run, confirmed against authoritative sources
and handled explicitly: French INSEE (`1 85 03 75 116 001 27`), Swedish
personnummer's full-century form (`19960804-5820`), Dutch BSN
(`1234.56.789`), Spanish NIF/NIE (`12345678-Z`), and Australian TFN
(`123 456 782`) - in addition to IBAN and UK NINO, mentioned above. Not
every remaining rule has been checked for a real alternate display format
this thoroughly yet (e.g. Norwegian, Hungarian) - if you know of one,
please open an issue or PR.

## Known limitations

- **NER is English-only and unreliable on other languages.** The bundled
  spaCy model (`en_core_web_sm`) was trained on English. On non-English
  text it will miss most names/places, and can misclassify ordinary words
  as PERSON/ORGANIZATION (e.g. Spanish "gobierno"/"trimestre" flagged as
  ORGANIZATION in testing). Regex rules (email, phone, credit card, etc.)
  are largely language-agnostic and still work. For non-English documents,
  treat NER output as noisy and either spot-check carefully or use
  `use_ner=False` and rely on regex rules alone. Emails were reliably
  redacted across every language tested (English, Spanish, French, German,
  Chinese, Arabic, Japanese); name/location detection was not.
- **Rare NER false positives on placeholder/non-name text** (e.g. spaCy
  occasionally tags "Lorem ipsum" boilerplate as PERSON). Harmless in
  practice, but a reminder that NER output isn't ground truth.
- **Generic NER on real documents misses things.** spaCy's small English
  model can fail to recognize a name with no surrounding sentence context
  (e.g. a signer's name alone on a line in a letter footer), even when it
  gets the same name right in a full sentence. A structural heuristic
  catches some of these (a short all-caps line next to a detected address
  is treated as a place name), but this isn't exhaustive.
- **Dense technical content (resumes/CVs, skills lists) can be
  over-redacted.** Found by testing against a real technical resume: a
  bulleted list of tool/framework names (Docker, jQuery, Neo4j, etc.) is
  full of capitalized, proper-noun-shaped tokens that a generic NER model
  frequently misreads as PERSON or ORGANIZATION - one real resume had 25
  false PERSON matches before mitigation. A curated exclusion list
  (`nonpii_terms.py`) fixes the common cases, but it's a fixed list, not
  a general solution - an unlisted framework/tool name can still get
  swept up. Contributions adding more terms are welcome.
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
