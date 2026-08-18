# pii-scrubber: step-by-step walkthrough

This walkthrough is generated directly from a real, passing run of the CLI (see `tools/record_demo.py`) — every command and output below is the actual output produced by that run, not hand-written.

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

## 2. Scrub a document and preview the redacted text + a summary count, without writing any file.

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

## 3. Write a redacted copy of the file, format preserved.

```console
$ pii-scrubber redact patient_intake.txt
Wrote patient_intake_redacted.txt
```

## 4. Confirm the original PII is gone from the redacted file.

```console
$ cat patient_intake_redacted.txt
Patient Intake Form

Name: [PERSON]: [EMAIL]
Phone: [PHONE]
SSN: [SSN]
Employer: [ORGANIZATION], located in [LOCATION].
```
