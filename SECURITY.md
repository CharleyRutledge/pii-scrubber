# Security & Privacy

## Reporting a missed detection or a false sense of safety

If pii-scrubber fails to redact real PII, or a redacted file leaks PII in
a way that isn't obvious (e.g. metadata, hidden layers, thumbnails), please
report it privately rather than in a public issue - a public report is a
roadmap for exactly what a document leaks.

Use GitHub's [private vulnerability reporting](https://github.com/CharleyRutledge/pii-scrubber/security/advisories/new)
for this repo, or open an issue that describes the *category* of the gap
(e.g. "UK phone numbers aren't matched", "EXIF GPS data in JPEGs isn't
stripped") without attaching real documents or real PII values.

## What this tool does and doesn't guarantee

- **No detector is complete.** Regex and NER both have known blind spots -
  see the README's "Known limitations" section. Always spot-check
  redacted output before sharing it, especially for anything sensitive.
- **This tool does not call any external service.** Detection runs
  entirely locally (regex + a local spaCy model; OCR, if enabled, runs
  against a local Tesseract install). No document content, file paths, or
  detected entities are sent anywhere by this library.
- **This is not legal or compliance advice.** Whether a given redaction
  is sufficient for GDPR, HIPAA, or another regulatory regime depends on
  your specific data and obligations - this tool is one input to that
  decision, not a substitute for it.
