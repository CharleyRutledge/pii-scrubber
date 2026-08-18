"""Diagnostic tool (not a pytest suite): runs scrub() over a hand-built
corpus of documents spanning multiple languages and both PII-bearing and
PII-free content, then reports:

  - MISSED: an expected PII substring that survived redaction (false negative)
  - LEAKED: an expected-PII substring correctly matched but incompletely
    redacted (rare, kept separate for clarity)
  - OVER-REDACTED: a substring that should have stayed but got replaced

This is exploratory - it prints a report for a human to read, it doesn't
assert. Real bugs found this way get fixed in the library and get a
proper regression test in tests/.

Usage: python tools/audit_corpus.py
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from pii_scrubber import scrub  # noqa: E402


@dataclass
class Case:
    id: str
    language: str
    text: str
    must_redact: list[str] = field(default_factory=list)  # substrings that must NOT survive
    must_keep: list[str] = field(default_factory=list)     # substrings that must survive


CASES: list[Case] = [
    Case(
        "en_business_email",
        "English",
        "Hi team,\n\n"
        "Please loop in Sarah Connor (sarah.connor@skynet-corp.com, "
        "310-555-0147) before we finalize the Q3 budget. She's based out "
        "of our Los Angeles office at 1200 Sunset Blvd.\n\n"
        "Thanks,\nJohn",
        must_redact=["sarah.connor@skynet-corp.com", "310-555-0147"],
        must_keep=["Q3 budget", "Thanks"],
    ),
    Case(
        "en_news_no_pii",
        "English",
        "The central bank raised interest rates by a quarter point on "
        "Wednesday, citing persistent inflation pressures. Markets reacted "
        "cautiously, with the S&P 500 closing roughly flat.",
        must_redact=[],
        must_keep=["central bank", "S&P 500", "inflation"],
    ),
    Case(
        "en_lorem_ipsum",
        "English",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do "
        "eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        must_redact=[],
        must_keep=["Lorem ipsum", "consectetur"],
    ),
    Case(
        "en_code_snippet",
        "English (code)",
        "def connect(host='127.0.0.1', port=5432):\n"
        "    user = get_current_user()\n"
        "    return Database(host, port, user)\n",
        must_redact=[],
        must_keep=["def connect", "get_current_user", "Database"],
    ),
    Case(
        "es_business_email",
        "Spanish",
        "Hola equipo,\n\n"
        "Por favor contacten a Maria Garcia (maria.garcia@empresa.es, "
        "+34 612 345 678) antes del viernes. Su oficina esta en Madrid.\n\n"
        "Saludos",
        must_redact=["maria.garcia@empresa.es"],
        must_keep=["Saludos", "viernes"],
    ),
    Case(
        "es_news_no_pii",
        "Spanish",
        "El gobierno anuncio nuevas medidas economicas para reducir la "
        "inflacion durante el proximo trimestre, segun fuentes oficiales.",
        must_redact=[],
        must_keep=["gobierno", "inflacion", "trimestre"],
    ),
    Case(
        "fr_business_letter",
        "French",
        "Bonjour,\n\n"
        "Merci de contacter Pierre Dubois a pierre.dubois@societe.fr ou "
        "au 06 12 34 56 78 pour toute question concernant le contrat.\n\n"
        "Cordialement",
        must_redact=["pierre.dubois@societe.fr"],
        must_keep=["Cordialement", "contrat"],
    ),
    Case(
        "fr_recipe_no_pii",
        "French",
        "Faites revenir les oignons dans l'huile d'olive pendant cinq "
        "minutes, puis ajoutez l'ail et laissez mijoter a feu doux.",
        must_redact=[],
        must_keep=["oignons", "huile d'olive", "feu doux"],
    ),
    Case(
        "de_official_letter",
        "German",
        "Sehr geehrte Damen und Herren,\n\n"
        "Bitte wenden Sie sich an Herrn Klaus Mueller unter "
        "klaus.mueller@firma.de oder 030 12345678 bezueglich Ihrer "
        "Anfrage.\n\n"
        "Mit freundlichen Gruessen",
        must_redact=["klaus.mueller@firma.de"],
        must_keep=["Anfrage", "Mit freundlichen"],
    ),
    Case(
        "de_product_no_pii",
        "German",
        "Dieses Produkt besteht aus recyceltem Aluminium und ist fuer den "
        "industriellen Einsatz bei Temperaturen bis zu 200 Grad geeignet.",
        must_redact=[],
        must_keep=["Aluminium", "industriellen", "Temperaturen"],
    ),
    Case(
        "zh_business_card",
        "Chinese (Simplified)",
        "姓名：李雷\n"
        "邮箱：li.lei@example.com.cn\n"
        "电话：138-0013-8000\n"
        "地址：北京市朝阳区",
        must_redact=["li.lei@example.com.cn"],
        must_keep=[],
    ),
    Case(
        "zh_paragraph_no_pii",
        "Chinese (Simplified)",
        "今天天气非常好，适合出去散步。",
        must_redact=[],
        must_keep=["天气"],
    ),
    Case(
        "ar_email",
        "Arabic",
        "مرحبا،\n"
        "يرجى التواصل مع "
        "أحمد خالد عبر "
        "ahmed.khaled@example.com أو الهاتف "
        "0501234567",
        must_redact=["ahmed.khaled@example.com"],
        must_keep=[],
    ),
    Case(
        "ja_contact",
        "Japanese",
        "お問い合わせは以下まで：\n"
        "メール：tanaka.taro@example.co.jp\n"
        "電話：090-1234-5678",
        must_redact=["tanaka.taro@example.co.jp"],
        must_keep=[],
    ),
    Case(
        "mixed_multilingual",
        "English + Spanish",
        "The meeting notes: 'Gracias, Juan Perez' was heard at the close. "
        "Contact juan.perez@example.com or 555-234-9981 for the recording.",
        must_redact=["juan.perez@example.com", "555-234-9981"],
        must_keep=["meeting notes", "recording"],
    ),
]


def run() -> int:
    issues = 0
    for case in CASES:
        result = scrub(case.text, use_ner=True)
        redacted = result.text

        missed = [s for s in case.must_redact if s in redacted]
        over_redacted = [s for s in case.must_keep if s not in redacted]

        status = "OK"
        if missed or over_redacted:
            status = "ISSUES"
            issues += 1

        print(f"=== [{status}] {case.id} ({case.language}) ===")
        print(f"counts: {result.counts}")
        if missed:
            print(f"  MISSED (should have been redacted): {missed}")
        if over_redacted:
            print(f"  OVER-REDACTED (should have survived): {over_redacted}")
        print()

    print(f"{len(CASES)} cases, {issues} with issues.")
    return issues


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
