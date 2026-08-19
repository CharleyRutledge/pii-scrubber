"""Passport detection via the Machine Readable Zone (MRZ), the two-line
block of capital letters, digits, and `<` fill characters printed on the
photo page of every passport worldwide (ICAO Document 9303 TD3 format).
This is used instead of a per-country passport-number regex: passport
number formats vary hugely by issuing country and mostly have no public
checksum of their own, so a bare "9 alphanumeric characters" pattern would
be far too collision-prone. The MRZ, by contrast, is identical in
structure across every issuing country and carries four real ICAO check
digits, giving genuine precision regardless of which country issued it.

Algorithm and field layout verified against ICAO 9303's own published
worked example (passport number "L898902C3", DOB 740812, expiry 120415 -
each check digit below was independently computed and confirmed to match
the standard's documented values before this was wired into detection).
"""

import re

from .entities import EntityMatch

_MRZ_VALUES = {c: 10 + i for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
_MRZ_VALUES.update({str(d): d for d in range(10)})
_MRZ_VALUES["<"] = 0
_MRZ_WEIGHTS = (7, 3, 1)


def _mrz_check_digit(s: str) -> int:
    total = sum(_MRZ_VALUES[ch] * _MRZ_WEIGHTS[i % 3] for i, ch in enumerate(s))
    return total % 10


def _check_digit_matches(field: str, digit_char: str) -> bool:
    if digit_char == "<":
        digit_char = "0"
    if not digit_char.isdigit():
        return False
    return _mrz_check_digit(field) == int(digit_char)


# TD3 (passport) MRZ: two 44-character lines.
# Line 1: "P" + subtype + 3-letter issuing country + name field.
# Line 2: passport number(9) + check(1) + nationality(3) + DOB(6) + check(1)
#         + sex(1) + expiry(6) + check(1) + personal number(14) + check(1)
#         + composite check(1).
_MRZ_LINE1 = re.compile(r"^P[A-Z<][A-Z<]{3}[A-Z<]{39}$")
_MRZ_LINE2 = re.compile(r"^[A-Z0-9<]{9}[0-9]([A-Z<]{3})(\d{6})(\d)([MF<])(\d{6})(\d)([A-Z0-9<]{14})([0-9<])(\d)$")


def _validate_line2(line2: str) -> bool:
    match = _MRZ_LINE2.match(line2)
    if not match:
        return False

    passport_number = line2[0:9]
    passport_check = line2[9]
    _nationality, dob, dob_check, _sex, expiry, expiry_check, personal_number, personal_check, composite_check = (
        match.groups()
    )

    if not _check_digit_matches(passport_number, passport_check):
        return False
    if not _check_digit_matches(dob, dob_check):
        return False
    if not _check_digit_matches(expiry, expiry_check):
        return False

    composite_field = passport_number + passport_check + dob + dob_check + expiry + expiry_check + personal_number + personal_check
    return _check_digit_matches(composite_field, composite_check)


def find_passport_matches(text: str) -> list[EntityMatch]:
    """Finds ICAO 9303 TD3 passport MRZ blocks (two adjacent 44-char lines)
    with valid check digits, anywhere in the text.
    """
    matches: list[EntityMatch] = []
    lines = text.splitlines(keepends=True)

    line_starts = []
    cursor = 0
    for line in lines:
        line_starts.append(cursor)
        cursor += len(line)

    for i in range(len(lines) - 1):
        line1 = lines[i].rstrip("\r\n")
        line2 = lines[i + 1].rstrip("\r\n")

        if len(line1) != 44 or len(line2) != 44:
            continue
        if not _MRZ_LINE1.match(line1):
            continue
        if not _validate_line2(line2):
            continue

        start = line_starts[i]
        end = line_starts[i + 1] + len(line2)
        full_text = lines[i].rstrip("\r\n") + "\n" + line2
        matches.append(EntityMatch("PASSPORT_MRZ", full_text, start, end, source="regex"))

    return matches
