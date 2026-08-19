"""Generates many synthetic documents per country using Faker's
locale-aware (and, for several countries, checksum-correct) ID/phone/
address generators, runs scrub() over each, and reports the detection
rate per country/field. Exploratory, not a pytest suite - prints a report.

Usage: python tools/audit_national_ids.py
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from faker import Faker  # noqa: E402
from pii_scrubber import scrub  # noqa: E402

# locale -> (country name, our rule label, faker method to call for the ID
# - "ssn" unless noted, None if faker has no real generator to validate
# against for this country - see tests/test_national_ids.py instead)
LOCALES = {
    "en_US": ("United States", "SSN", "ssn"),
    "en_GB": ("United Kingdom", "UK_NINO", None),  # faker only emits reserved "ZZ" prefix
    "fr_FR": ("France", "FR_INSEE", "ssn"),
    "nl_NL": ("Netherlands", "NL_BSN", "ssn"),
    "pl_PL": ("Poland", "PL_PESEL", "ssn"),
    "pt_BR": ("Brazil", "BR_CPF", "ssn"),
    "zh_CN": ("China", "CN_RESIDENT_ID", "ssn"),
    "ko_KR": ("South Korea", "KR_RRN", None),  # faker doesn't implement the real checksum
    "en_CA": ("Canada", "CA_SIN", "ssn"),
    "sv_SE": ("Sweden", "SE_PERSONNUMMER", "ssn"),
    "de_DE": ("Germany", "DE_RVNR", "rvnr"),
    "es_ES": ("Spain", "ES_NIF", "nif"),
    "it_IT": ("Italy", "IT_CODICE_FISCALE", "ssn"),
    "no_NO": ("Norway", "NO_FODSELSNUMMER", "ssn"),
    "tr_TR": ("Turkey", "TR_TCKN", "ssn"),
    "ro_RO": ("Romania", "RO_CNP", "ssn"),
    "hu_HU": ("Hungary", "HU_SZEMELYI", "ssn"),
    "ru_RU": ("Russia", "RU_INN", None),  # faker's ssn() is 12 random digits, no checksum
    "pt_PT": ("Portugal", "PT_NIF", None),  # faker has no NIF generator
    "en_AU": ("Australia", "AU_TFN", None),  # faker has no en_AU ssn provider
    "ar_DZ": ("Algeria", "DZ_NIN", "ssn"),
    "de_AT": ("Austria", "AT_SVNR", "ssn"),
    "el_GR": ("Greece", "EL_AMKA", "ssn"),
    "es_MX": ("Mexico", "MX_IMSS", "ssn"),
    "et_EE": ("Estonia", "EE_ISIKUKOOD", "ssn"),
    "fi_FI": ("Finland", "FI_HETU", "ssn"),
    "fr_CH": ("Switzerland", "CH_AHV", "ssn"),
    "he_IL": ("Israel", "IL_TZ", "ssn"),
    "hr_HR": ("Croatia", "HR_OIB", "ssn"),
    "lv_LV": ("Latvia", "LV_PERSONAS_KODS", "ssn"),
    "mk_MK": ("North Macedonia", "MK_EMBG", "ssn"),
    "nl_BE": ("Belgium", "BE_RRN", "ssn"),
    "sr_BA": ("Bosnia and Herzegovina", "BA_JMB", "ssn"),
    "uk_UA": ("Ukraine", "UA_RNOKPP", "ssn"),
    "zh_TW": ("Taiwan", "TW_ID", "ssn"),
    "en_IN": ("India", "IN_AADHAAR", "aadhaar_id"),
    "es_CL": ("Chile", "CL_RUT", "person_rut"),
    "cs_CZ": ("Czech Republic", "CZ_SK_RODNE_CISLO", "birth_number"),
    "sk_SK": ("Slovakia", "CZ_SK_RODNE_CISLO", "birth_number"),
}

DOCS_PER_LOCALE = 10


def build_document(fake: Faker, id_method: str) -> tuple[str, dict]:
    name = fake.name()
    email = fake.email()
    phone = fake.phone_number()
    national_id = getattr(fake, id_method)()
    address = fake.address().replace("\n", ", ")

    text = (
        f"Applicant: {name}\n"
        f"Email: {email}\n"
        f"Phone: {phone}\n"
        f"National ID: {national_id}\n"
        f"Address: {address}\n"
    )
    return text, {"name": name, "email": email, "phone": phone, "national_id": national_id}


def run() -> None:
    total_docs = 0
    email_hits = 0
    national_id_hits = 0
    national_id_expected = 0
    by_country: dict[str, dict] = {}

    for locale, (country, id_label, id_method) in LOCALES.items():
        fake = Faker(locale)
        Faker.seed(42)
        country_email_hits = 0
        country_id_hits = 0

        for _ in range(DOCS_PER_LOCALE):
            text, fields = build_document(fake, id_method or "ssn")
            result = scrub(text, use_ner=False)  # regex-only: isolates rule coverage
            total_docs += 1

            if fields["email"] not in result.text:
                email_hits += 1
                country_email_hits += 1

            if id_method is not None:
                national_id_expected += 1
                if fields["national_id"] not in result.text:
                    national_id_hits += 1
                    country_id_hits += 1

        by_country[country] = {
            "id_rule": id_label,
            "email_rate": f"{country_email_hits}/{DOCS_PER_LOCALE}",
            "id_rate": (
                f"{country_id_hits}/{DOCS_PER_LOCALE}" if id_method else "(see unit tests)"
            ),
        }

    print(f"{total_docs} synthetic documents generated across {len(LOCALES)} countries.\n")
    print(f"{'Country':<16} {'ID rule':<20} {'Email caught':<14} {'National ID caught'}")
    for country, stats in by_country.items():
        print(f"{country:<16} {stats['id_rule']:<20} {stats['email_rate']:<14} {stats['id_rate']}")

    print(
        f"\nOverall: email {email_hits}/{total_docs}, "
        f"national ID {national_id_hits}/{national_id_expected} "
        f"(only counted where faker can generate a real checksummed ID)."
    )
    print(
        "\nRows marked '(see unit tests)' have no faker generator that "
        "produces a real, checksum-valid ID for that country - either "
        "faker has no provider (Australia), only implements a partial/"
        "reserved-value generator (UK, South Korea, Russia), or has no "
        "matching field at all (Portugal). Those rules are verified "
        "instead with hand-computed test vectors in "
        "tests/test_national_ids.py."
    )
    print(
        "\nHungary is occasionally ~9/10 rather than 10/10: faker's own "
        "hu_HU generator can compute a checksum value of 10 and then emit "
        "it as the literal two characters '10' (unlike its Norwegian "
        "provider, which explicitly rejects/retries that case), producing "
        "a 12-character string that isn't a valid real 11-digit Hungarian "
        "ID in the first place - our rule correctly does not match it."
    )


if __name__ == "__main__":
    run()
