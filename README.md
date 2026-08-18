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
pip install -e ".[all]"   # pdf + docx support
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

### Disabling NER

Regex-only mode skips loading the spaCy model, useful when you only care
about structured identifiers or want to avoid the model dependency:

```python
scrub(text, use_ner=False)
```

### Detected entity types

| Label | Source |
|---|---|
| EMAIL, PHONE, SSN, CREDIT_CARD, IP_ADDRESS, MAC_ADDRESS, IBAN | regex |
| PERSON, LOCATION, ORGANIZATION, AFFILIATION | spaCy NER |

## Development

```bash
pytest
```
