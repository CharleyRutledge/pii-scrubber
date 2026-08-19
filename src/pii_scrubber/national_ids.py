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
# mapped to 19/18 for the checksum calculation. Real documents (payslips,
# tax notices) conventionally group this with spaces, e.g.
# "1 85 03 75 116 001 27" - found missing (same class of bug as the earlier
# IBAN/UK NINO spacing fixes) by deliberately re-testing that lesson against
# every other space-prone rule after being asked what else was missed.
_FR_INSEE = re.compile(
    r"\b([12])[ ]?(\d{2})[ ]?(\d{2}|20|30|40|50|60|70|80|90|99)"
    r"[ ]?(\d{2}|2[AaBb])[ ]?(\d{3})[ ]?(\d{3})[ ]?(\d{2})\b"
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
# Official documents conventionally group the 9-digit form with dots as
# "NNNN.NN.NNN" (confirmed via government.nl/business.gov.nl), which the
# original digit-only pattern missed - the same class of bug as the
# IBAN/UK NINO/FR INSEE/SE personnummer spacing fixes.
_NL_BSN = re.compile(r"(?<!\d)(?:\d{4}\.\d{2}\.\d{3}|\d{8,9})(?!\d)")


def _nl_bsn_ok(raw: str) -> bool:
    digits = raw.replace(".", "")
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
# YYMMDD-XXXX (or +XXXX for centenarians) is the short form, but official
# documents commonly use the full-century 12-digit form YYYYMMDD-XXXX too -
# missing that was the same class of spacing/format bug as IBAN/UK NINO/
# French INSEE above, just with an optional prefix instead of internal
# spaces. Luhn-validated on the 10-digit short form; the optional 2-digit
# century prefix is excluded from the checksum per the official spec.
_SE_PERSONNUMMER = re.compile(r"(?<!\d)(?:\d{2})?\d{6}[-+]\d{4}(?!\d)")


def _se_personnummer_ok(raw: str) -> bool:
    digits = re.sub(r"[-+]", "", raw)
    if len(digits) == 12:
        digits = digits[2:]
    return _luhn_ok(digits)


# ---------- Spanish NIF / NIE ----------
# NIF: 8 digits + a checksum letter looked up from `number % 23`.
# NIE (foreign residents): a leading X/Y/Z letter (standing in for 0/1/2 in
# the checksum calculation) + 7 digits + the same checksum letter.
# Commonly displayed with a dash before the check letter ("12345678-Z"),
# which the original pattern missed - same class of bug as the other
# spacing/format fixes above.
_ES_CONTROL_LOOKUP = "TRWAGMYFPDXBNJZSQVHLCKE"

_ES_NIF = re.compile(r"\b\d{8}-?[A-Za-z]\b")
_ES_NIE = re.compile(r"\b[XYZxyz]-?\d{7}-?[A-Za-z]\b")


def _es_nif_ok(raw: str) -> bool:
    raw = raw.replace("-", "")
    digits, letter = raw[:8], raw[8].upper()
    return _ES_CONTROL_LOOKUP[int(digits) % 23] == letter


def _es_nie_ok(raw: str) -> bool:
    raw = raw.replace("-", "")
    prefix_value = "XYZ".index(raw[0].upper())
    digits, letter = raw[1:8], raw[8].upper()
    return _ES_CONTROL_LOOKUP[int(str(prefix_value) + digits) % 23] == letter


# ---------- Italian Codice Fiscale ----------
# 16 chars: 6 letters (surname/name consonants) + 2 digits (year) + 1 letter
# (month, from a fixed set) + 2 digits (day, +40 for female) + 4 alphanumeric
# (municipality code) + 1 checksum letter. Checksum sums a lookup value per
# character - a different table depending on whether its position (1-based)
# is odd or even - mod 26, mapped to a letter. Tables are the standard
# published Codice Fiscale checksum tables.
_IT_CODICE_FISCALE = re.compile(
    r"\b[A-Za-z]{6}\d{2}[ABCDEHLMPRSTabcdehlmprst]\d{2}[A-Za-z]\d{3}[A-Za-z]\b"
)

_IT_ALPHANUMERICS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# Indices 0-9 = digits 0-9, 10-35 = letters A-Z, matching _IT_ALPHANUMERICS.
_IT_ODD_TABLE = (
    1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21,
    2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23,
)
_IT_EVEN_TABLE = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
)


def _it_codice_fiscale_ok(raw: str) -> bool:
    value = raw.upper()
    total = 0
    for index, char in enumerate(value[:15]):
        char_index = _IT_ALPHANUMERICS.index(char)
        table = _IT_ODD_TABLE if index % 2 == 0 else _IT_EVEN_TABLE
        total += table[char_index]
    expected = chr(65 + total % 26)
    return value[15] == expected


# ---------- Norwegian Fodselsnummer ----------
# 11 digits: DDMMYY + 3-digit individual number + 2 check digits, validated
# with a two-stage Modulus 11 checksum.
_NO_FODSELSNUMMER = re.compile(r"(?<!\d)\d{11}(?!\d)")

_NO_SCALE1 = (3, 7, 6, 1, 8, 9, 4, 5, 2)
_NO_SCALE2 = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def _no_checksum(digits: list, scale: tuple) -> int:
    value = 11 - (sum(d * s for d, s in zip(digits, scale)) % 11)
    return 0 if value == 11 else value


def _no_fodselsnummer_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    k1 = _no_checksum(digits[:9], _NO_SCALE1)
    k2 = _no_checksum(digits[:9] + [k1], _NO_SCALE2)
    return k1 != 10 and k2 != 10 and digits[9] == k1 and digits[10] == k2


# ---------- Turkish TC Kimlik No ----------
# 11 digits. 10th digit = ((sum of odd-position digits * 7) - sum of
# even-position digits) mod 10; 11th digit = (sum of first 10 digits) mod 10.
_TR_TCKN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")


def _tr_tckn_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    odd_sum = sum(digits[i] for i in (0, 2, 4, 6, 8))
    even_sum = sum(digits[i] for i in (1, 3, 5, 7))
    tenth = ((odd_sum * 7) - even_sum) % 10
    eleventh = sum(digits[:10]) % 10
    return digits[9] == tenth and digits[10] == eleventh


# ---------- Romanian CNP ----------
# 13 digits, weighted checksum (weights 2,7,9,1,4,6,3,5,8,2,7,9), remainder
# 10 maps to check digit 1.
_RO_CNP = re.compile(r"(?<!\d)[1-8]\d{12}(?!\d)")

_RO_WEIGHTS = (2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9)


def _ro_cnp_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    total = sum(d * w for d, w in zip(digits[:12], _RO_WEIGHTS)) % 11
    check = 1 if total == 10 else total
    return digits[12] == check


# ---------- Hungarian szemelyi szam ----------
# 11 digits: gender(1) + birth YYMMDD(6) + serial(3) + check digit(1). The
# check-digit weighting direction flips based on the (2-digit) birth year
# encoded in the number: ascending weights 1..10 when 17 < year < 97,
# descending weights 10..1 otherwise. This matches the reference
# implementation's actual code, which is the opposite of what its own
# docstring claims ("born <=1999 -> ascending") - the docstring appears to
# describe an intended/documented scheme that doesn't match what the code
# actually does, so the real generator's behavior (verified against
# thousands of generated examples) was used as the source of truth instead.
_HU_SZEMELYI = re.compile(r"(?<!\d)[1-8]\d{10}(?!\d)")


def _hu_szemelyi_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    year = digits[1] * 10 + digits[2]
    if 17 < year < 97:
        weighted = sum((i + 1) * d for i, d in enumerate(digits[:10]))
    else:
        weighted = sum((10 - i) * d for i, d in enumerate(digits[:10]))
    return digits[10] == weighted % 11


# ---------- Russian INN (individual taxpayer number) ----------
# 12 digits, two sequential weighted-mod-11 check digits.
_RU_INN = re.compile(r"(?<!\d)\d{12}(?!\d)")

_RU_WEIGHTS_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_RU_WEIGHTS_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _ru_inn_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    check11 = sum(d * w for d, w in zip(digits[:10], _RU_WEIGHTS_11)) % 11 % 10
    check12 = sum(d * w for d, w in zip(digits[:11], _RU_WEIGHTS_12)) % 11 % 10
    return digits[10] == check11 and digits[11] == check12


# ---------- Portuguese NIF ----------
# 9 digits, weighted checksum (weights 9,8,7,6,5,4,3,2), remainder <2 maps
# to check digit 0.
_PT_NIF = re.compile(r"(?<!\d)[1-9]\d{8}(?!\d)")

_PT_WEIGHTS = (9, 8, 7, 6, 5, 4, 3, 2)


def _pt_nif_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    total = sum(d * w for d, w in zip(digits[:8], _PT_WEIGHTS))
    remainder = total % 11
    check = 0 if remainder < 2 else 11 - remainder
    return digits[8] == check


# ---------- Australian Tax File Number ----------
# 9 digits, weighted checksum (weights 1,4,3,7,5,8,6,9,10) divisible by 11.
# The ATO's own correspondence displays this grouped in 3s ("123 456 782"),
# not just the compact form - same class of bug as the other spacing fixes.
_AU_TFN = re.compile(r"(?<!\d)(?:\d{9}|\d{3} \d{3} \d{3})(?!\d)")

_AU_WEIGHTS = (1, 4, 3, 7, 5, 8, 6, 9, 10)


def _au_tfn_ok(raw: str) -> bool:
    digits = [int(c) for c in raw if c.isdigit()]
    total = sum(d * w for d, w in zip(digits, _AU_WEIGHTS))
    return total % 11 == 0


# ---------- German Rentenversicherungsnummer (pension insurance number) ----------
# 12 chars: 2 digits (area) + 6 digits (DDMMYY birthdate) + 1 letter (first
# letter of birth surname) + 2 digits + 1 check digit. Checksum: the letter
# is converted to its 2-digit alphabet position (A=01..Z=26), expanding the
# value to 12 digits, each multiplied by a fixed factor, digit-summed, and
# totalled mod 10.
_DE_RVNR = re.compile(r"\b\d{8}[A-Za-z]\d{3}\b")

_DE_RVNR_FACTORS = (2, 1, 2, 5, 7, 1, 2, 1, 2, 1, 2, 1)


def _de_rvnr_ok(raw: str) -> bool:
    value = raw.upper()
    check_digit = int(value[11])
    letter_pos = ord(value[8]) - ord("A") + 1
    expanded = value[:8] + f"{letter_pos:02d}" + value[9:11]
    if not expanded.isdigit() or len(expanded) != 12:
        return False

    total = 0
    for digit_char, factor in zip(expanded, _DE_RVNR_FACTORS):
        product = int(digit_char) * factor
        total += sum(int(d) for d in str(product))
    return total % 10 == check_digit


# ---------- Algerian NIN (National Identification Number) ----------
# 18 digits, modified-Luhn 2-digit control key over the first 16.
_DZ_NIN = re.compile(r"(?<!\d)\d{18}(?!\d)")


def _dz_nin_control_key(base: str) -> str:
    total, alternate = 0, False
    for i in range(len(base) - 1, -1, -1):
        d = int(base[i]) * (2 if alternate else 1)
        total += d - 9 if d > 9 else d
        alternate = not alternate
    remainder = total % 10
    return f"{(0 if remainder == 0 else 10 - remainder):02d}"


def _dz_nin_ok(raw: str) -> bool:
    return raw[16:] == _dz_nin_control_key(raw[:16])


# ---------- Austrian Sozialversicherungsnummer ----------
# 10 digits: 3-digit serial + 1 check digit + 6-digit birthdate (DDMMYY),
# weighted mod-11 checksum computed over the 9 digits excluding the check
# digit itself (which sits at position 3, not the end).
_AT_SVNR = re.compile(r"(?<!\d)\d{10}(?!\d)")

_AT_SVNR_WEIGHTS = (3, 7, 9, 5, 8, 4, 2, 1, 6)


def _at_svnr_ok(raw: str) -> bool:
    check_digit = int(raw[3])
    base = raw[:3] + raw[4:]
    total = sum(int(d) * w for d, w in zip(base, _AT_SVNR_WEIGHTS))
    return total % 11 == check_digit


# ---------- Greek AMKA (social security number) ----------
# 11 digits: DDMMYY birthdate + 4-digit serial + 1 Luhn check digit.
_EL_AMKA = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _el_amka_ok(raw: str) -> bool:
    return _luhn_ok(raw)


# ---------- Mexican IMSS Social Security Number ----------
# 11 digits: office(2) + start-year(2) + birth-year(2) + serial(4) + 1
# check digit, using a digital-root-based checksum.
_MX_IMSS = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _digital_root_reduce(n: int) -> int:
    if n == 0:
        return 0
    if n % 9 == 0:
        return 9
    return n % 9


def _mx_imss_ok(raw: str) -> bool:
    base = [int(c) for c in raw[:10]]
    computed = -sum(_digital_root_reduce(n * (i % 2 + 1)) for i, n in enumerate(base)) % 10
    return computed == int(raw[10])


# ---------- Estonian Isikukood ----------
# 11 digits: century/sex(1) + DDMMYY(6) + serial(3) + 1 check digit, using
# a two-scale mod-11 checksum (falls back to a second weight scale if the
# first attempt's remainder is 10).
_EE_ISIKUKOOD = re.compile(r"(?<!\d)[1-8]\d{10}(?!\d)")

_EE_SCALE1 = (1, 2, 3, 4, 5, 6, 7, 8, 9, 1)
_EE_SCALE2 = (3, 4, 5, 6, 7, 8, 9, 1, 2, 3)


def _ee_isikukood_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    total = sum(d * w for d, w in zip(digits[:10], _EE_SCALE1)) % 11
    if total >= 10:
        total = sum(d * w for d, w in zip(digits[:10], _EE_SCALE2)) % 11
        total = 0 if total == 10 else total
    return digits[10] == total


# ---------- Finnish Henkilotunnus (HETU) ----------
# DDMMYY + century sign (+/-/A) + 3-digit serial + 1 checksum character
# (base-31 alphabet). Not purely numeric, so needs its own pattern rather
# than joining the bare-digit-run rules below.
_FI_HETU = re.compile(r"(?<!\d)\d{6}[-+A]\d{3}[0-9A-FHJ-NPR-Y](?!\d)")
_FI_CHECKSUM_ALPHABET = "0123456789ABCDEFHJKLMNPRSTUVWXY"


def _fi_hetu_ok(raw: str) -> bool:
    date_part, rest = raw[:6], raw[7:]
    serial, check_char = rest[:3], rest[3]
    numeric_value = int(date_part + serial)
    return _FI_CHECKSUM_ALPHABET[numeric_value % 31] == check_char.upper()


# ---------- Swiss AHV/AVS Number ----------
# 13 digits, always starting with the fixed "756" (Switzerland's GS1
# country prefix) - about as distinctive/low-collision a shape as a
# national ID gets. Conventionally grouped "756.XXXX.XXXX.XX"; EAN-13-style
# checksum (odd/even weighted sum).
_CH_AHV = re.compile(r"(?<!\d)756\.?\d{4}\.?\d{4}\.?\d{2}(?!\d)")


def _ch_ahv_ok(raw: str) -> bool:
    digits = [int(c) for c in raw if c.isdigit()]
    if len(digits) != 13:
        return False
    evensum = sum(digits[:-1:2])
    oddsum = sum(digits[1:-1:2])
    expected = (10 - ((evensum + oddsum * 3) % 10)) % 10
    return digits[-1] == expected


# ---------- Israeli Teudat Zehut ----------
# 9 digits, a Luhn-family checksum (doubles digits at 0-based odd
# positions within the 8-digit body, from the left).
_IL_TZ = re.compile(r"(?<!\d)\d{9}(?!\d)")


def _il_tz_ok(raw: str) -> bool:
    digits = raw.zfill(9)
    total = 0
    for i in range(0, 8, 2):
        total += int(digits[i])
        doubled = int(digits[i + 1]) * 2
        total += doubled if doubled <= 9 else doubled - 9
    last_digit = (10 - total % 10) % 10
    return int(digits[8]) == last_digit


# ---------- Croatian OIB ----------
# 11 digits, ISO 7064 MOD 11,10 checksum (an iterative running-remainder
# algorithm, not a fixed-weight dot product).
_HR_OIB = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _iso7064_mod_11_10(digits: list) -> int:
    remainder = 10
    for digit in digits:
        remainder = (remainder + digit) % 10
        if remainder == 0:
            remainder = 10
        remainder = (remainder * 2) % 11
    control_digit = 11 - remainder
    return 0 if control_digit == 10 else control_digit


def _hr_oib_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    return digits[10] == _iso7064_mod_11_10(digits[:10])


# ---------- Latvian Personas Kods ----------
# "DDMMYY-CZZZQ": 6-digit birthdate, dash, century digit, 3-digit serial,
# 1 check digit - weighted mod-11 checksum with a wraparound adjustment.
_LV_PERSONAS_KODS = re.compile(r"(?<!\d)\d{6}-\d{5}(?!\d)")

_LV_WEIGHTS = (1, 6, 3, 7, 9, 10, 5, 8, 4, 2)


def _lv_personas_kods_ok(raw: str) -> bool:
    digits = raw.replace("-", "")
    base = [int(c) for c in digits[:10]]
    weighted_sum = sum(d * w for d, w in zip(base, _LV_WEIGHTS))
    remainder = (1 - weighted_sum) % 11
    if remainder == 10:
        remainder = 0
    elif remainder < 0:
        remainder += 11
    return int(digits[10]) == remainder


# ---------- North Macedonian EMBG / Bosnian JMB ----------
# 13 digits, weighted mod-11 checksum. Both descend from the shared
# former-Yugoslav JMBG numbering system and use the same weights, but their
# reference implementations handle one edge case differently: when the
# weighted sum mod 11 is exactly 1, North Macedonia's algorithm maps it to
# check digit 0, while Bosnia's treats that combination as genuinely
# unallocatable (no valid check digit exists). Verified against both
# countries' faker providers directly rather than assumed identical - an
# initial version of this code wrongly shared one function between them,
# which silently rejected ~1/11 of otherwise-valid North Macedonian numbers.
_MK_EMBG = re.compile(r"(?<!\d)\d{13}(?!\d)")

_JMBG_WEIGHTS = (7, 6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def _mk_embg_checksum(digits: list) -> int:
    total = sum(w * d for w, d in zip(_JMBG_WEIGHTS, digits))
    remainder = 11 - (total % 11)
    return 0 if remainder in (10, 11) else remainder


def _ba_jmb_checksum(digits: list) -> int | None:
    total = sum(w * d for w, d in zip(_JMBG_WEIGHTS, digits))
    remainder = total % 11
    if remainder == 0:
        return 0
    if remainder == 1:
        return None
    return 11 - remainder


def _mk_embg_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    return digits[12] == _mk_embg_checksum(digits[:12])


def _ba_jmb_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    expected = _ba_jmb_checksum(digits[:12])
    return expected is not None and digits[12] == expected


# ---------- Belgian Rijksregisternummer ----------
# 11 digits: 6-digit birthdate + 3-digit sequence + 2-digit checksum
# (mod 97, with births in 2000+ requiring the 9-digit base to be offset by
# 2 billion before the mod-97 calculation - both interpretations are tried
# since the digits alone don't reveal which century was intended).
_BE_RRN = re.compile(r"(?<!\d)\d{11}(?!\d)")


def _be_rrn_ok(raw: str) -> bool:
    base, check = int(raw[:9]), int(raw[9:])
    if 97 - (base % 97) == check:
        return True
    return 97 - ((base + 2_000_000_000) % 97) == check


# ---------- Ukrainian RNOKPP (taxpayer identification number) ----------
# 10 digits, weighted mod-11 mod-10 checksum over the first 9.
_UA_RNOKPP = re.compile(r"(?<!\d)\d{10}(?!\d)")

_UA_WEIGHTS = (-1, 5, 7, 9, 4, 6, 10, 5, 7)


def _ua_rnokpp_ok(raw: str) -> bool:
    digits = [int(c) for c in raw]
    total = sum(d * w for d, w in zip(digits[:9], _UA_WEIGHTS))
    return digits[9] == total % 11 % 10


# ---------- Taiwanese National ID ----------
# 1 letter + 9 digits (10 chars total). The leading letter is converted to
# a 2-digit value via a fixed table, then combined with the digits under a
# positional-weight checksum.
_TW_ID = re.compile(r"\b[A-Za-z][12]\d{7}\d\b")

_TW_LETTER_WEIGHTS = {
    **{c: 10 + i for i, c in enumerate("ABCDEFGH")},
    "I": 34,
    **{c: 18 + i for i, c in enumerate("JKLMN")},
    "O": 35,
    **{c: 23 + i for i, c in enumerate("PQRSTUV")},
    "W": 32,
    "X": 30,
    "Y": 31,
    "Z": 33,
}


def _tw_id_ok(raw: str) -> bool:
    value = raw.upper()
    letter_value = _TW_LETTER_WEIGHTS[value[0]]
    total = (letter_value % 10) * 9 + letter_value // 10
    for i, ch in enumerate(value[1:], start=1):
        weight = 9 - i if i < 9 else 1
        total += int(ch) * weight
    return total % 10 == 0


_CHECKSUM_RULES = [
    ("CA_SIN", _CA_SIN, lambda m: _ca_sin_ok(m.group())),
    ("SE_PERSONNUMMER", _SE_PERSONNUMMER, lambda m: _se_personnummer_ok(m.group())),
    ("KR_RRN", _KR_RRN, lambda m: _kr_rrn_ok(m.group())),
    ("BR_CPF", _BR_CPF, lambda m: _br_cpf_ok(m.group())),
    ("FR_INSEE", _FR_INSEE, _fr_insee_ok),
    ("ES_NIF", _ES_NIF, lambda m: _es_nif_ok(m.group())),
    ("ES_NIE", _ES_NIE, lambda m: _es_nie_ok(m.group())),
    ("IT_CODICE_FISCALE", _IT_CODICE_FISCALE, lambda m: _it_codice_fiscale_ok(m.group())),
    ("DE_RVNR", _DE_RVNR, lambda m: _de_rvnr_ok(m.group())),
    ("FI_HETU", _FI_HETU, lambda m: _fi_hetu_ok(m.group())),
    ("CH_AHV", _CH_AHV, lambda m: _ch_ahv_ok(m.group())),
    ("LV_PERSONAS_KODS", _LV_PERSONAS_KODS, lambda m: _lv_personas_kods_ok(m.group())),
    ("TW_ID", _TW_ID, lambda m: _tw_id_ok(m.group())),
]

# Plain-digit-run formats (no distinctive punctuation) are checked last and
# only if nothing more specific already matched that span, since e.g. a
# bare 11-digit run could coincidentally be Polish, Norwegian, or just a
# long reference number - the checksum is doing all the precision work here.
_DIGIT_RUN_RULES = [
    ("NL_BSN", _NL_BSN, lambda digits: _nl_bsn_ok(digits)),
    ("PL_PESEL", _PL_PESEL, lambda digits: _pl_pesel_ok(digits)),
    ("NO_FODSELSNUMMER", _NO_FODSELSNUMMER, lambda digits: _no_fodselsnummer_ok(digits)),
    ("TR_TCKN", _TR_TCKN, lambda digits: _tr_tckn_ok(digits)),
    ("RO_CNP", _RO_CNP, lambda digits: _ro_cnp_ok(digits)),
    ("HU_SZEMELYI", _HU_SZEMELYI, lambda digits: _hu_szemelyi_ok(digits)),
    ("RU_INN", _RU_INN, lambda digits: _ru_inn_ok(digits)),
    ("PT_NIF", _PT_NIF, lambda digits: _pt_nif_ok(digits)),
    ("AU_TFN", _AU_TFN, lambda digits: _au_tfn_ok(digits)),
    ("DZ_NIN", _DZ_NIN, lambda digits: _dz_nin_ok(digits)),
    ("AT_SVNR", _AT_SVNR, lambda digits: _at_svnr_ok(digits)),
    ("EL_AMKA", _EL_AMKA, lambda digits: _el_amka_ok(digits)),
    ("MX_IMSS", _MX_IMSS, lambda digits: _mx_imss_ok(digits)),
    ("EE_ISIKUKOOD", _EE_ISIKUKOOD, lambda digits: _ee_isikukood_ok(digits)),
    ("IL_TZ", _IL_TZ, lambda digits: _il_tz_ok(digits)),
    ("HR_OIB", _HR_OIB, lambda digits: _hr_oib_ok(digits)),
    ("MK_EMBG", _MK_EMBG, lambda digits: _mk_embg_ok(digits)),
    # Bosnian JMB is the same 13-digit shape as North Macedonia's EMBG
    # (both former-Yugoslav JMBG numbers) but uses its own checksum
    # function - see the note above _mk_embg_checksum/_ba_jmb_checksum for
    # the one case where they actually differ.
    ("BA_JMB", _MK_EMBG, lambda digits: _ba_jmb_ok(digits)),
    ("BE_RRN", _BE_RRN, lambda digits: _be_rrn_ok(digits)),
    ("UA_RNOKPP", _UA_RNOKPP, lambda digits: _ua_rnokpp_ok(digits)),
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
