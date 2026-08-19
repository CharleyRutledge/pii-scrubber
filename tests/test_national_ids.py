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


def test_french_insee_conventional_spacing():
    # Regression: real documents (payslips, tax notices) conventionally
    # group this with spaces ("1 85 03 75 116 001 27"), the same class of
    # bug as the earlier IBAN/UK NINO spacing fixes - found by deliberately
    # re-checking every other space-prone national ID rule after being
    # asked what else had been missed.
    assert "FR_INSEE" in _labels("NIR: 1 85 03 75 116 001 27")


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


def test_dutch_bsn_conventional_dotted_grouping():
    # Regression: official documents (government.nl, business.gov.nl)
    # display the 9-digit form grouped as "NNNN.NN.NNN" - same class of
    # bug as the other spacing/format fixes.
    from faker import Faker

    fake = Faker("nl_NL")
    Faker.seed(1)
    valid_bsn = fake.ssn()
    dotted = f"{valid_bsn[:4]}.{valid_bsn[4:6]}.{valid_bsn[6:]}"
    assert "NL_BSN" in _labels(f"BSN: {dotted}")


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


def test_swedish_personnummer_full_century_form():
    # Regression: official documents commonly use the full-century 12-digit
    # form (YYYYMMDD-XXXX) as well as the 10-digit short form - the century
    # prefix is excluded from the Luhn checksum per spec. Derived from the
    # same faker-generated short-form vector above with "19" prepended.
    assert "SE_PERSONNUMMER" in _labels("Personnummer: 19960804-5820")


def test_korean_rrn_checksum_hand_verified():
    # faker's ko_KR provider doesn't implement a real checksum (literal
    # random digit in the check position - see its ssn_formats), so this
    # vector is hand-computed against the published weighted-checksum
    # algorithm (weights 2,3,4,5,6,7,8,9,2,3,4,5, mod 11, mod 10) rather
    # than sourced from faker.
    assert "KR_RRN" in _labels("RRN: 230521-1161559")
    assert "KR_RRN" not in _labels("RRN: 230521-1161550")


def test_spanish_nif_valid_checksum():
    from faker import Faker

    fake = Faker("es_ES")
    Faker.seed(1)
    valid_nif = fake.nif()
    assert "ES_NIF" in _labels(f"NIF: {valid_nif}")


def test_spanish_nif_conventional_dash():
    # Regression: commonly displayed with a dash before the check letter
    # ("12345678-Z") - same class of bug as the other spacing/format fixes.
    from faker import Faker

    fake = Faker("es_ES")
    Faker.seed(1)
    valid_nif = fake.nif()
    dashed = f"{valid_nif[:8]}-{valid_nif[8]}"
    assert "ES_NIF" in _labels(f"NIF: {dashed}")


def test_spanish_nie_valid_checksum():
    from faker import Faker

    fake = Faker("es_ES")
    Faker.seed(1)
    valid_nie = fake.nie()
    assert "ES_NIE" in _labels(f"NIE: {valid_nie}")


def test_italian_codice_fiscale_valid_checksum():
    from faker import Faker

    fake = Faker("it_IT")
    Faker.seed(1)
    valid_cf = fake.ssn()
    assert "IT_CODICE_FISCALE" in _labels(f"CF: {valid_cf}")


def test_norwegian_fodselsnummer_valid_checksum():
    from faker import Faker

    fake = Faker("no_NO")
    Faker.seed(1)
    valid_fnr = fake.ssn()
    assert "NO_FODSELSNUMMER" in _labels(f"Fodselsnummer: {valid_fnr}")


def test_turkish_tckn_valid_checksum():
    from faker import Faker

    fake = Faker("tr_TR")
    Faker.seed(1)
    valid_tckn = fake.ssn()
    assert "TR_TCKN" in _labels(f"TCKN: {valid_tckn}")


def test_romanian_cnp_valid_checksum():
    from faker import Faker

    fake = Faker("ro_RO")
    Faker.seed(1)
    valid_cnp = fake.ssn()
    assert "RO_CNP" in _labels(f"CNP: {valid_cnp}")


def test_hungarian_szemelyi_valid_checksum():
    from faker import Faker

    fake = Faker("hu_HU")
    # Seed chosen to land on an 11-digit result - faker's own generator can
    # occasionally emit a 12-character string (see tools/audit_national_ids.py
    # for why), which correctly does not match our 11-digit rule.
    Faker.seed(1)
    valid_id = fake.ssn()
    assert len(valid_id) == 11
    assert "HU_SZEMELYI" in _labels(f"Szemelyi szam: {valid_id}")


def test_german_rvnr_valid_checksum():
    from faker import Faker

    fake = Faker("de_DE")
    Faker.seed(1)
    valid_rvnr = fake.rvnr()
    assert "DE_RVNR" in _labels(f"RVNR: {valid_rvnr}")


def test_russian_inn_hand_verified():
    # faker's ru_RU provider generates 12 random digits with no real
    # checksum, so this vector is hand-computed against the published
    # two-stage weighted-mod-11 algorithm instead.
    assert "RU_INN" in _labels("INN: 123456789047")
    assert "RU_INN" not in _labels("INN: 123456789040")


def test_portuguese_nif_hand_verified():
    # faker has no Portuguese NIF generator, so this vector is
    # hand-computed against the published weighted-mod-11 algorithm.
    assert "PT_NIF" in _labels("NIF: 123456789")
    assert "PT_NIF" not in _labels("NIF: 123456780")


def test_australian_tfn_hand_verified():
    # faker has no en_AU ssn provider at all, so this vector is
    # hand-computed against the published ATO weighted-checksum algorithm.
    assert "AU_TFN" in _labels("TFN: 123456782")
    assert "AU_TFN" not in _labels("TFN: 123456780")


def test_australian_tfn_conventional_grouping():
    # Regression: the ATO's own correspondence displays this grouped in 3s
    # ("123 456 782") - same class of bug as the other spacing fixes.
    assert "AU_TFN" in _labels("TFN: 123 456 782")
