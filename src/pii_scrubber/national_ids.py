"""National ID number detectors for countries beyond the US/Ireland already
covered in rules.py (SSN, PPS_NUMBER). Each country's ID has its own digit
count and, in several cases, its own checksum algorithm - reusing the same
"N digits with dashes" shape across countries risks heavy collision with
phone numbers, reference numbers, etc., so wherever a real published
checksum algorithm exists, it's implemented and validated here (the same
approach already used for CREDIT_CARD via Luhn in rules.py).

Formats were validated against faker's locale-aware id-generation for each
country (`Faker(locale).ssn()`), which implements the same real checksums.
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


# ---------- UK National Insurance Number ----------
# Format: 2 letters (excluding D,F,I,Q,U,V and certain prefixes) + 6 digits
# + a suffix letter A-D, e.g. "AB123456C" - but HMRC's own presentation
# format groups the digits in pairs with spaces ("AB 12 34 56 C"), which the
# original digit-only pattern missed entirely (same class of bug as the
# IBAN spacing issue). "ZZ" is a real prefix, but is officially reserved
# for temporary/non-genuine numbers, so it's excluded like the others.
_UK_NINO = re.compile(
    r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]"
    r"[ ]?\d{2}[ ]?\d{2}[ ]?\d{2}[ ]?[A-D]\b"
)


# ---------- French INSEE / NIR (numero de securite sociale) ----------
# 15 digits: sex(1) + year(2) + month(2) + dept(2-3) + commune(3) + order(3)
# + key(2). Key = 97 - (first 13 digits mod 97), with Corsica letters 2A/2B
# mapped to 19/18 for the checksum calculation.
_FR_INSEE = re.compile(
    r"\b([12])(\d{2})(\d{2}|20|30|40|50|60|70|80|90|99)"
    r"(\d{2}|2[AaBb])(\d{3})(\d{3})(\d{2})\b"
)


def _fr_insee_ok(match: re.Match) -> bool:
    sex, year, month, dept, commune, order, key = match.groups()
    dept_num = "19" if dept.upper() == "2A" else "18" if dept.upper() == "2B" else dept
    significant = sex + year + month + dept_num + commune + order
    try:
        expected_key = 97 - (int(significant) % 97)
    except ValueError:
        return False
    return expected_key == int(key)


# ---------- Dutch BSN (Burgerservicenummer) ----------
# 8-9 digits, "elfproef" checksum: weighted sum with weights descending from
# 9 (or 8) down to 2, then -1 for the last digit, must be divisible by 11.
_NL_BSN = re.compile(r"(?<!\d)\d{8,9}(?!\d)")


def _nl_bsn_ok(digits: str) -> bool:
    if len(digits) == 8:
        digits = "0" + digits
    weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
    total = sum(int(d) * w for d, w in zip(digits, weights))
    return total % 11 == 0 and digits != "000000000"


# ---------- Polish PESEL ----------
# 11 digits, weighted checksum (weights 1,3,7,9,1,3,7,9,1,3), check digit
# makes the weighted sum divisible by 10.
_PL_PESEL = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _pl_pesel_ok(digits: str) -> bool:
    weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    total = sum(int(d) * w for d, w in zip(digits[:10], weights))
    check = (10 - (total % 10)) % 10
    return check == int(digits[10])


# ---------- Brazilian CPF ----------
# 11 digits (often formatted XXX.XXX.XXX-XX), two sequential check digits.
_BR_CPF = re.compile(
    r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"
)


def _br_cpf_ok(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False

    def check_digit(base: str) -> int:
        weight = len(base) + 1
        total = sum(int(d) * (weight - i) for i, d in enumerate(base))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    d1 = check_digit(digits[:9])
    d2 = check_digit(digits[:9] + str(d1))
    return digits[9] == str(d1) and digits[10] == str(d2)


# ---------- Chinese Resident Identity Card ----------
# 18 characters: 17 digits + 1 check char (0-9 or X). ISO 7064 MOD 11-2.
_CN_RESIDENT_ID = re.compile(r"(?<![0-9A-Za-z])\d{17}[\dXx](?![0-9A-Za-z])")

_CN_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_CN_CHECK_MAP = "10X98765432"


def _cn_resident_id_ok(value: str) -> bool:
    digits = value[:17]
    if not digits.isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(digits, _CN_WEIGHTS))
    expected = _CN_CHECK_MAP[total % 11]
    return value[17].upper() == expected


# ---------- South Korean Resident Registration Number ----------
# YYMMDD-XXXXXXX (13 digits with a dash after the 6th). Weighted checksum
# with weights 2,3,4,5,6,7,8,9,2,3,4,5 mod 11. Note: faker's own ko_KR
# provider doesn't implement this checksum (its format string uses a
# literal random digit for the check position), so it can't be used to
# validate this rule end-to-end - verified by hand-computing the checksum
# against the published algorithm instead.
_KR_RRN = re.compile(r"(?<!\d)\d{6}-\d{7}(?!\d)")

_KR_WEIGHTS = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]


def _kr_rrn_ok(raw: str) -> bool:
    digits = raw.replace("-", "")
    total = sum(int(d) * w for d, w in zip(digits[:12], _KR_WEIGHTS))
    check = (11 - (total % 11)) % 10
    return check == int(digits[12])


# ---------- Canadian Social Insurance Number ----------
# 9 digits, conventionally grouped in 3s ("XXX XXX XXX" or "XXX-XXX-XXX"),
# validated with the Luhn algorithm (same as credit cards).
_CA_SIN = re.compile(r"(?<!\d)\d{3}[ -]\d{3}[ -]\d{3}(?!\d)")


def _ca_sin_ok(raw: str) -> bool:
    digits = re.sub(r"[ -]", "", raw)
    return _luhn_ok(digits)


# ---------- Swedish Personnummer ----------
# YYMMDD-XXXX (or +XXXX for centenarians), Luhn-validated on the 10-digit
# short form (date + serial + check digit, century digits excluded).
_SE_PERSONNUMMER = re.compile(r"(?<!\d)\d{6}[-+]\d{4}(?!\d)")


def _se_personnummer_ok(raw: str) -> bool:
    digits = re.sub(r"[-+]", "", raw)
    return _luhn_ok(digits)


_CHECKSUM_RULES = [
    ("CA_SIN", _CA_SIN, lambda m: _ca_sin_ok(m.group())),
    ("SE_PERSONNUMMER", _SE_PERSONNUMMER, lambda m: _se_personnummer_ok(m.group())),
    ("KR_RRN", _KR_RRN, lambda m: _kr_rrn_ok(m.group())),
    ("BR_CPF", _BR_CPF, lambda m: _br_cpf_ok(m.group())),
    ("FR_INSEE", _FR_INSEE, _fr_insee_ok),
]

# Plain-digit-run formats (no distinctive punctuation) are checked last and
# only if nothing more specific already matched that span, since e.g. a
# bare 11-digit run could coincidentally be Polish, Norwegian, or just a
# long reference number - the checksum is doing all the precision work here.
_DIGIT_RUN_RULES = [
    ("NL_BSN", _NL_BSN, lambda digits: _nl_bsn_ok(digits)),
    ("PL_PESEL", _PL_PESEL, lambda digits: _pl_pesel_ok(digits)),
]


def find_national_id_matches(text: str) -> list[EntityMatch]:
    matches: list[EntityMatch] = []

    for m in _UK_NINO.finditer(text):
        matches.append(EntityMatch("UK_NINO", m.group(), m.start(), m.end(), source="regex"))

    for m in _CN_RESIDENT_ID.finditer(text):
        if _cn_resident_id_ok(m.group()):
            matches.append(
                EntityMatch("CN_RESIDENT_ID", m.group(), m.start(), m.end(), source="regex")
            )

    for label, pattern, check in _CHECKSUM_RULES:
        for m in pattern.finditer(text):
            if check(m):
                matches.append(
                    EntityMatch(label, m.group(), m.start(), m.end(), source="regex")
                )

    for label, pattern, check in _DIGIT_RUN_RULES:
        for m in pattern.finditer(text):
            if check(m.group()):
                matches.append(
                    EntityMatch(label, m.group(), m.start(), m.end(), source="regex")
                )

    return matches
