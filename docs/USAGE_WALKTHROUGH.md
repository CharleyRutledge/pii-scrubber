# pii-scrubber: step-by-step walkthrough

This walkthrough is generated directly from a real, passing run of the CLI (see `tools/record_demo.py`) - every command and output below is the actual output produced by that run, not hand-written.

![demo](assets/demo.gif)

## 1. See what the CLI offers.

```console
$ pii-scrubber --help
Usage: pii-scrubber [OPTIONS] COMMAND [ARGS]...

  Scrub PII from documents, locally, before you paste/upload them elsewhere.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  redact  Write a redacted copy of PATH in its original file format.
  scrub   Print PII-redacted text extracted from PATH, plus a summary count.
```

## 2. Scrub a plain text file and preview the redacted text + a summary count, without writing any file.

```console
$ pii-scrubber scrub patient_intake.txt
Patient Intake Form

Name: [PERSON]: [EMAIL]
Phone: [PHONE]
SSN: [SSN]
Employer: [ORGANIZATION], located in [LOCATION].


Found:
  EMAIL: 1
  LOCATION: 1
  ORGANIZATION: 1
  PERSON: 1
  PHONE: 1
  SSN: 1
```

## 3. Scrub a Markdown file and preview the redacted text + a summary count, without writing any file.

```console
$ pii-scrubber scrub notes.md
# Follow-up notes

Reach **Jane Doe** at [EMAIL] or [PHONE] before the Friday deadline.


Found:
  EMAIL: 1
  PHONE: 1
```

## 4. Scrub a HTML file and preview the redacted text + a summary count, without writing any file.

```console
$ pii-scrubber scrub profile.html

Contact card
[PERSON]
LinkedIn: [SOCIAL_PROFILE]



Found:
  PERSON: 1
  SOCIAL_PROFILE: 1
```

## 5. Scrub a CSV file and preview the redacted text + a summary count, without writing any file.

```console
$ pii-scrubber scrub contacts.csv
name, email, phone
[PERSON], [EMAIL], [PHONE]
[PERSON], [EMAIL], [PHONE]

Found:
  EMAIL: 2
  PERSON: 2
  PHONE: 2
```

## 6. Scrub a JSON file and preview the redacted text + a summary count, without writing any file.

```console
$ pii-scrubber scrub record.json
[PERSON]
[EMAIL]
[PHONE]

Found:
  EMAIL: 1
  PERSON: 1
  PHONE: 1
```

## 7. Scrub a Word (.docx) file and preview the redacted text + a summary count, without writing any file.

```console
$ pii-scrubber scrub letter.docx
Employment Letter
This confirms [PERSON] ([EMAIL], [PHONE]) is employed at [ORGANIZATION]

Found:
  EMAIL: 1
  ORGANIZATION: 1
  PERSON: 1
  PHONE: 1
```

## 8. Scrub a PDF file and preview the redacted text + a summary count, without writing any file.

```console
$ pii-scrubber scrub notice.pdf
Please contact [PERSON] at [EMAIL] or [PHONE].


Found:
  EMAIL: 1
  PERSON: 1
  PHONE: 1
```

## 9. Write a redacted copy of the file, format preserved.

```console
$ pii-scrubber redact patient_intake.txt
Wrote patient_intake_redacted.txt
```

## 10. Confirm the original PII is gone from the redacted file.

```console
$ cat patient_intake_redacted.txt
Patient Intake Form

Name: [PERSON]: [EMAIL]
Phone: [PHONE]
SSN: [SSN]
Employer: [ORGANIZATION], located in [LOCATION].
```
