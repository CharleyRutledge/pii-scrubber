"""Regex-based detectors for structured PII (emails, phones, IDs, etc.).

Each rule is a (label, compiled_pattern) pair. Patterns are deliberately
conservative about false positives where possible (e.g. credit cards use a
Luhn check) since scrubbed output is meant to stay readable.
"""

import re
from typing import Iterator

from .entities import EntityMatch


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

_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)

_IPV6 = re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{0,4}\b")

_US_PASSPORT = re.compile(r"(?<![A-Za-z0-9])[A-Z]{1,2}\d{6,9}(?![A-Za-z0-9])")

_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")

_MAC_ADDRESS = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")


def _find_credit_cards(text: str) -> Iterator[re.Match]:
    for m in _CREDIT_CARD.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            yield m


_SIMPLE_RULES = [
    ("EMAIL", _EMAIL),
    ("PHONE", _PHONE),
    ("SSN", _SSN),
    ("IP_ADDRESS", _IPV4),
    ("IP_ADDRESS", _IPV6),
    ("MAC_ADDRESS", _MAC_ADDRESS),
    ("IBAN", _IBAN),
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

    return matches
