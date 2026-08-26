"""Regex-based detectors for structured PII (emails, phones, IDs, etc.).

Each rule is a (label, compiled_pattern) pair. Patterns are deliberately
conservative about false positives where possible (e.g. credit cards use a
Luhn check) since scrubbed output is meant to stay readable.
"""

import re
from typing import Iterator

from .entities import EntityMatch
from .mrz import find_passport_matches
from .national_ids import find_national_id_matches


def _luhn_ok(digits: str) -> bool:
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_PHONE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
)

_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

_CREDIT_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

# Masked card number as commonly displayed by banks/payment processors,
# e.g. "Card: 416598******4764" - reveals the BIN (first 4-6 digits,
# which identifies the issuing bank) and last 4 digits. The digits aren't
# a contiguous run (the asterisks break it up), so _CREDIT_CARD's Luhn
# check never even sees it as a candidate - found via a real bank
# statement where every masked card reference sailed through unredacted.
_MASKED_CARD = re.compile(r"(?<!\w)\d{4,6}\*{2,12}\d{4}(?!\w)")

_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)

_IPV6 = re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{0,4}\b")

# Passport numbers are NOT implemented: a generic "1-2 letters + 6-9 digits"
# shape (the old draft attempted here) is far too collision-prone against
# invoice numbers, SKUs, and order references to ship without much tighter
# per-country constraints or a checksum - modern US passports, for
# instance, are just 9 plain digits with no distinguishing shape at all.
# Flagged as a real gap rather than left as silently-unwired dead code -
# see README's Known limitations and CONTRIBUTING.md.

# IBANs are conventionally displayed grouped in 4s with spaces (ISO 13616
# presentation format, e.g. "GB29 NWBK 6016 1331 9268 19"), not as one
# unbroken string - found by testing against a real invoice where the
# compact-only pattern silently missed a space-formatted IBAN entirely.
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b")

_MAC_ADDRESS = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")

# Irish PPS Number: 7 digits + a checksum letter, optionally + a second
# letter that's always A or W, e.g. "8516676H", "1234567HA". No word-boundary
# anchors, so it still catches copies glued to junk text/watermarks
# (e.g. "gfd8516676Hgfd") - the fixed A/W second letter keeps the match tight
# instead of greedily eating trailing junk letters.
_PPS_NUMBER = re.compile(r"(?<!\d)\d{7}[A-Za-z](?:[AaWw])?")

# Irish Eircode: routing key (letter + 2 alnum) + space + 4-char unique id,
# e.g. "V94 275E", "D01 YT32". Uses a literal space, not bare \s - found via
# a real CV where the employer name "G4S" was immediately followed by a
# newline and then a year ("G4S\n2019"), which \s's newline-matching let
# through as a false Eircode, hiding a real company name under a
# misleading label.
_EIRCODE = re.compile(r"\b[A-Za-z]\d[0-9A-Za-z] [0-9A-Za-z]{4}\b")

# A short window of text around a common street-type suffix is treated as an
# address. Deliberately NOT anchored to line boundaries (^...$) - text that's
# been reconstructed without real newlines (e.g. OCR word-joining) would
# otherwise match from the first such keyword to the last, potentially
# swallowing the entire document. Bounding the context window keeps the
# blast radius small regardless of whether real line breaks are present.
#
# Split into two groups by ambiguity, rather than one case-sensitive list:
# some suffix words (Close, Court, Park, Row, Way, Place) double as common
# English words ("at the close of the meeting") and stay Title-Case/ALL-CAPS
# only to avoid the false positives that caused the original case-sensitive
# fix. The rest (Road, Cottages, Terrace, ...) aren't ordinary English words
# in their own right, so they're matched case-insensitively - found via a
# real bank statement whose extracted address text ("47 quins cottages",
# " road") was all-lowercase and silently missed entirely by the fully
# case-sensitive version of this rule.
_ADDRESS_SUFFIXES_ANY_CASE = [
    "Road", "Rd", "Street", "St", "Avenue", "Ave", "Lane", "Ln", "Drive", "Dr",
    "Cottages", "Terrace", "Square", "Sq", "Grove", "Crescent", "Walk",
    "Boulevard", "Blvd",
]
_ADDRESS_SUFFIXES_TITLE_CASE_ONLY = [
    "Way", "Close", "Court", "Ct", "Place", "Pl", "Park", "Row",
]
_ANY_CASE_PATTERN = "|".join(f"{w}\\.?" for w in _ADDRESS_SUFFIXES_ANY_CASE)
_TITLE_CASE_PATTERN = "|".join(
    f"{w}\\.?|{w.upper()}\\.?" for w in _ADDRESS_SUFFIXES_TITLE_CASE_ONLY
)
_ADDRESS_SUFFIX_PATTERN = rf"(?i:{_ANY_CASE_PATTERN})|(?:{_TITLE_CASE_PATTERN})"
_ADDRESS_LINE = re.compile(
    rf"[^\n]{{0,40}}\b(?:{_ADDRESS_SUFFIX_PATTERN})\b[^\n]{{0,40}}"
)

# Title-prefixed personal name, e.g. "Mr. Jane Doe" or "MR CHARLEY RUTLEDGE".
# Catches names spaCy's NER misses on all-caps text.
_TITLED_NAME = re.compile(
    r"\b(?:[Mm][Rr]|[Mm][Rr][Ss]|[Mm][Ss]|[Mm][Ii][Ss][Ss]|[Mm][Xx]|[Dd][Rr]|[Pp][Rr][Oo][Ff])\.?"
    r"\s+[A-Z][A-Za-z'-]*(?:\s+[A-Z][A-Za-z'-]*){1,3}\b"
)

# file:// URIs - often leak a local OS username via the path, e.g.
# "file:///C:/Users/jane/Downloads/resume.pdf".
_FILE_URI = re.compile(r"\bfile:/{1,3}[^\s<>\"')\]]+", re.IGNORECASE)

# URLs with an explicit scheme.
_SCHEME_URL = re.compile(r"\b(?:https?|ftp)://[^\s<>\"')\]]+", re.IGNORECASE)

# Personal/professional profile links without a scheme, e.g.
# "linkedin.com/in/charleyr", "github.com/charleyr".
_PROFILE_URL = re.compile(
    r"\b(?:www\.)?(?:linkedin\.com/in|linkedin\.com/company|github\.com|"
    r"gitlab\.com|twitter\.com|x\.com|behance\.net|dribbble\.com)/[A-Za-z0-9\-_/%.]+",
    re.IGNORECASE,
)


def _find_credit_cards(text: str) -> Iterator[re.Match]:
    for m in _CREDIT_CARD.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            yield m


_SIMPLE_RULES = [
    ("EMAIL", _EMAIL),
    ("PHONE", _PHONE),
    ("CREDIT_CARD", _MASKED_CARD),
    ("SSN", _SSN),
    ("PPS_NUMBER", _PPS_NUMBER),
    ("IP_ADDRESS", _IPV4),
    ("IP_ADDRESS", _IPV6),
    ("MAC_ADDRESS", _MAC_ADDRESS),
    ("IBAN", _IBAN),
    ("EIRCODE", _EIRCODE),
    ("ADDRESS", _ADDRESS_LINE),
    ("PERSON", _TITLED_NAME),
    ("FILE_PATH", _FILE_URI),
    ("URL", _SCHEME_URL),
    ("SOCIAL_PROFILE", _PROFILE_URL),
]


def find_regex_matches(text: str) -> list[EntityMatch]:
    matches: list[EntityMatch] = []

    for label, pattern in _SIMPLE_RULES:
        for m in pattern.finditer(text):
            matches.append(
                EntityMatch(label, m.group(), m.start(), m.end(), source="regex")
            )

    for m in _find_credit_cards(text):
        matches.append(
            EntityMatch("CREDIT_CARD", m.group(), m.start(), m.end(), source="regex")
        )

    matches.extend(find_national_id_matches(text))
    matches.extend(find_passport_matches(text))

    return matches
