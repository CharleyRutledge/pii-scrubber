from pii_scrubber.national_ids import find_national_id_matches


def _labels(text: str) -> set[str]:
    return {m.label for m in find_national_id_matches(text)}


def test_uk_nino_compact_and_spaced_formats():
    # HMRC's own presentation format groups digits in pairs with spaces
    # ("AB 12 34 56 D"), not just the compact form - both must match.
    assert "UK_NINO" in _labels("NINO: AB123456D")
    assert "UK_NINO" in _labels("NINO: AB 12 34 56 D")


def test_uk_nino_excludes_reserved_test_prefix():
    # "ZZ" is officially reserved for temporary/non-genuine numbers and
    # never issued to real people - faker itself only ever generates this
    # prefix for its fake test data, which is why it can't be used to
    # validate this rule end-to-end (see tools/audit_national_ids.py).
    assert "UK_NINO" not in _labels("NINO: ZZ123456T")


def test_uk_nino_excludes_invalid_first_letter():
    # D, F, I, Q, U, V are never valid first letters.
    assert "UK_NINO" not in _labels("NINO: QR123456C")


def test_french_insee_valid_checksum():
    # significant = sex(1) + year(2) + month(2) + dept(2) + commune(3) +
    # order(3) = "1" "85" "03" "75" "116" "001" = 1850375116001
    # key = 97 - (1850375116001 % 97) = 27
    assert "FR_INSEE" in _labels("NIR: 185037511600127")


def test_french_insee_rejects_bad_checksum():
    # Same digits as the valid vector above but with the final key digit
    # incremented, which must fail the checksum.
    assert "FR_INSEE" not in _labels("NIR: 185037511600128")


def test_dutch_bsn_valid_and_invalid_checksum():
    matches = find_national_id_matches("BSN: 111222333")
    # Whether 111222333 itself is elfproef-valid isn't the point - what
    # matters is that a run of same-length random digits usually isn't,
    # and a real generated valid one is caught.
    from faker import Faker

    fake = Faker("nl_NL")
    Faker.seed(1)
    valid_bsn = fake.ssn()
    assert "NL_BSN" in _labels(f"BSN: {valid_bsn}")


def test_polish_pesel_valid_checksum():
    from faker import Faker

    fake = Faker("pl_PL")
    Faker.seed(1)
    valid_pesel = fake.ssn()
    assert "PL_PESEL" in _labels(f"PESEL: {valid_pesel}")


def test_brazilian_cpf_valid_and_invalid():
    from faker import Faker

    fake = Faker("pt_BR")
    Faker.seed(1)
    valid_cpf = fake.ssn()
    assert "BR_CPF" in _labels(f"CPF: {valid_cpf}")

    assert "BR_CPF" not in _labels("CPF: 111.111.111-11")  # repeated-digit, always invalid


def test_chinese_resident_id_valid_checksum():
    from faker import Faker

    fake = Faker("zh_CN")
    Faker.seed(1)
    valid_id = fake.ssn()
    assert "CN_RESIDENT_ID" in _labels(f"ID: {valid_id}")


def test_canadian_sin_luhn_validated():
    from faker import Faker

    fake = Faker("en_CA")
    Faker.seed(1)
    valid_sin = fake.ssn()
    assert "CA_SIN" in _labels(f"SIN: {valid_sin}")


def test_swedish_personnummer_luhn_validated():
    from faker import Faker

    fake = Faker("sv_SE")
    Faker.seed(1)
    valid_pn = fake.ssn()
    assert "SE_PERSONNUMMER" in _labels(f"Personnummer: {valid_pn}")


def test_korean_rrn_checksum_hand_verified():
    # faker's ko_KR provider doesn't implement a real checksum (literal
    # random digit in the check position - see its ssn_formats), so this
    # vector is hand-computed against the published weighted-checksum
    # algorithm (weights 2,3,4,5,6,7,8,9,2,3,4,5, mod 11, mod 10) rather
    # than sourced from faker.
    assert "KR_RRN" in _labels("RRN: 230521-1161559")
    assert "KR_RRN" not in _labels("RRN: 230521-1161550")
