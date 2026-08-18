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

# locale -> (country name, our label for that country's national ID rule,
# or None if we don't have a dedicated rule for it yet)
LOCALES = {
    "en_US": ("United States", "SSN"),
    "en_GB": ("United Kingdom", "UK_NINO"),
    "fr_FR": ("France", "FR_INSEE"),
    "nl_NL": ("Netherlands", "NL_BSN"),
    "pl_PL": ("Poland", "PL_PESEL"),
    "pt_BR": ("Brazil", "BR_CPF"),
    "zh_CN": ("China", "CN_RESIDENT_ID"),
    "ko_KR": ("South Korea", "KR_RRN"),
    "en_CA": ("Canada", "CA_SIN"),
    "sv_SE": ("Sweden", "SE_PERSONNUMMER"),
    # No dedicated national-ID rule yet - included to show current gaps.
    "de_DE": ("Germany", None),
    "es_ES": ("Spain", None),
    "it_IT": ("Italy", None),
    "no_NO": ("Norway", None),
    "ru_RU": ("Russia", None),
    "tr_TR": ("Turkey", None),
    "ro_RO": ("Romania", None),
    "hu_HU": ("Hungary", None),
    "pt_PT": ("Portugal", None),
    "en_AU": ("Australia", None),
}

DOCS_PER_LOCALE = 10


def build_document(fake: Faker) -> tuple[str, dict]:
    name = fake.name()
    email = fake.email()
    phone = fake.phone_number()
    national_id = fake.ssn()
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

    for locale, (country, id_label) in LOCALES.items():
        fake = Faker(locale)
        Faker.seed(42)
        country_email_hits = 0
        country_id_hits = 0

        for _ in range(DOCS_PER_LOCALE):
            text, fields = build_document(fake)
            result = scrub(text, use_ner=False)  # regex-only: isolates rule coverage
            total_docs += 1

            if fields["email"] not in result.text:
                email_hits += 1
                country_email_hits += 1

            if id_label is not None:
                national_id_expected += 1
                if fields["national_id"] not in result.text:
                    national_id_hits += 1
                    country_id_hits += 1

        by_country[country] = {
            "id_rule": id_label or "(none)",
            "email_rate": f"{country_email_hits}/{DOCS_PER_LOCALE}",
            "id_rate": (
                f"{country_id_hits}/{DOCS_PER_LOCALE}" if id_label else "n/a"
            ),
        }

    print(f"{total_docs} synthetic documents generated across {len(LOCALES)} countries.\n")
    print(f"{'Country':<16} {'ID rule':<18} {'Email caught':<14} {'National ID caught'}")
    for country, stats in by_country.items():
        print(f"{country:<16} {stats['id_rule']:<18} {stats['email_rate']:<14} {stats['id_rate']}")

    print(
        f"\nOverall: email {email_hits}/{total_docs}, "
        f"national ID {national_id_hits}/{national_id_expected} "
        f"(only counted for countries with a dedicated rule)."
    )
    print(
        "\nNote: UK and South Korea show low/zero hits here not because the "
        "rules are broken, but because faker's own generators can't be used "
        "to validate them - faker's en_GB provider deliberately only emits "
        "the officially-reserved 'ZZ' test prefix (which our rule correctly "
        "excludes, since it's never issued to real people), and faker's "
        "ko_KR provider doesn't implement the real checksum at all (literal "
        "random digit in the check position). Both rules were verified by "
        "hand against the published algorithms/formats instead - see "
        "tests/test_national_ids.py."
    )


if __name__ == "__main__":
    run()
