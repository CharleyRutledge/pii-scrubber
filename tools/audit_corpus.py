"""Diagnostic tool (not a pytest suite): runs scrub() over a hand-built
corpus of documents spanning many languages, document types, and PII
densities (none / low / medium / high / adversarial), then reports:

  - MISSED: an expected PII substring that survived redaction (false negative)
  - OVER-REDACTED: a substring that should have stayed but got replaced

This is exploratory - it prints a report for a human to read, it doesn't
assert. Real bugs found this way get fixed in the library and get a
proper regression test in tests/.

Usage: python tools/audit_corpus.py
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

# Corpus covers many non-Latin scripts (CJK, Cyrillic, Arabic, Devanagari,
# Thai). Windows consoles default to a legacy codepage that can't print
# most of them, so force UTF-8 on stdout rather than crash mid-report.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from pii_scrubber import scrub  # noqa: E402


@dataclass
class Case:
    id: str
    language: str
    doc_type: str
    density: str  # none | low | medium | high | adversarial
    text: str
    must_redact: list[str] = field(default_factory=list)  # substrings that must NOT survive
    must_keep: list[str] = field(default_factory=list)     # substrings that must survive


CASES: list[Case] = [
    # ---------- English: varied document types & densities ----------
    Case(
        "en_business_email", "English", "email", "medium",
        "Hi team,\n\n"
        "Please loop in Sarah Connor (sarah.connor@skynet-corp.com, "
        "310-555-0147) before we finalize the Q3 budget. She's based out "
        "of our Los Angeles office at 1200 Sunset Blvd.\n\n"
        "Thanks,\nJohn",
        must_redact=["sarah.connor@skynet-corp.com", "310-555-0147"],
        must_keep=["Q3 budget", "Thanks"],
    ),
    Case(
        "en_news_no_pii", "English", "news article", "none",
        "The central bank raised interest rates by a quarter point on "
        "Wednesday, citing persistent inflation pressures. Markets reacted "
        "cautiously, with the S&P 500 closing roughly flat.",
        must_keep=["central bank", "S&P 500", "inflation"],
    ),
    Case(
        "en_lorem_ipsum", "English", "placeholder text", "none",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do "
        "eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        must_keep=["Lorem ipsum", "consectetur"],
    ),
    Case(
        "en_code_snippet", "English", "source code", "none",
        "def connect(host='127.0.0.1', port=5432):\n"
        "    user = get_current_user()\n"
        "    return Database(host, port, user)\n",
        must_keep=["def connect", "get_current_user", "Database"],
    ),
    Case(
        "en_resume_high_density", "English", "resume/CV", "high",
        "MICHAEL ANDERSON\n"
        "123 Birchwood Drive, Austin, TX 78701\n"
        "michael.anderson87@gmail.com | (512) 555-0199\n"
        "LinkedIn: linkedin.com/in/michaelanderson87\n\n"
        "SUMMARY\n"
        "Senior software engineer with 8 years of experience in backend "
        "systems.\n\n"
        "EXPERIENCE\n"
        "Senior Engineer, Globex Corporation, 2021-Present\n"
        "Engineer, Initech, 2018-2021",
        must_redact=[
            "michael.anderson87@gmail.com", "(512) 555-0199",
            "linkedin.com/in/michaelanderson87",
        ],
        must_keep=["SUMMARY", "EXPERIENCE", "backend systems"],
    ),
    Case(
        "en_medical_note_high_density", "English", "medical record", "high",
        "Patient: Robert Chen, DOB unspecified.\n"
        "Contact: robert.chen@mail.com, 415-555-2210\n"
        "Address: 88 Fremont St, San Francisco, CA\n"
        "Insurance ID: SSN 987-65-4321 on file.\n"
        "Notes: patient reports mild headaches, prescribed ibuprofen.",
        must_redact=[
            "Robert Chen", "robert.chen@mail.com", "415-555-2210",
            "987-65-4321",
        ],
        must_keep=["mild headaches", "ibuprofen"],
    ),
    Case(
        "en_legal_clause_low_density", "English", "legal contract", "low",
        "WHEREAS the parties wish to enter into a confidentiality "
        "agreement covering all proprietary information exchanged during "
        "the course of this engagement, and WHEREAS both parties agree "
        "to binding arbitration in the event of a dispute, notices under "
        "this agreement shall be sent to legal@vendor-corp.com, and this "
        "agreement shall be governed by the laws of the State of Delaware "
        "without regard to its conflict of law provisions.",
        must_redact=["legal@vendor-corp.com"],
        # "State of Delaware" is correctly picked up as LOCATION - a
        # generic jurisdiction reference isn't sensitive, but the tool has
        # no way to distinguish that from an address without more context.
        must_keep=["WHEREAS", "binding arbitration"],
    ),
    Case(
        "en_invoice_high_density", "English", "invoice", "high",
        "INVOICE #INV-2024-00931\n"
        "Bill To: Karen Whitfield\n"
        "Email: karen.whitfield@customer.com\n"
        "Phone: 212-555-8834\n"
        "Card on file: 4111 1111 1111 1111\n"
        "Amount Due: $1,240.00",
        must_redact=[
            "karen.whitfield@customer.com", "212-555-8834",
            "4111 1111 1111 1111",
        ],
        must_keep=["Amount Due", "$1,240.00"],
    ),
    Case(
        "en_adversarial_lookalike_ids", "English", "product spec sheet", "adversarial",
        "Model No: 123-45-6789\n"
        "Firmware version: v4.13.2\n"
        "ISBN: 978-3-16-148410-0\n"
        "Server cluster ID: 10.0.0.1 (internal, non-routable)\n"
        "This device complies with FCC Part 15 regulations.",
        # Model No has the exact SSN shape - documenting current (imperfect)
        # behavior rather than asserting either way; internal IP is still a
        # real IP_ADDRESS match by design.
        # "FCC" is correctly recognized as a real organization name.
        must_keep=["Firmware version", "ISBN"],
    ),
    Case(
        "en_social_post_low_density", "English", "social media post", "low",
        "Just landed in Austin for the conference! So excited for the "
        "next few days of talks and networking. DM me if you want to "
        "grab coffee - reach me faster at 737-555-0143 though.",
        # "Austin" is correctly picked up as LOCATION - a city name
        # mentioned in passing, same tradeoff as the Delaware case above.
        must_redact=["737-555-0143"],
        must_keep=["conference", "networking"],
    ),
    Case(
        "en_support_ticket_medium_density", "English", "support ticket", "medium",
        "Ticket #48213\n"
        "Customer: Diane Foster (diane.foster@webmail.com)\n"
        "Issue: Unable to reset password. Account phone on file: "
        "646-555-7723.\n"
        "Status: Open",
        must_redact=["Diane Foster", "diane.foster@webmail.com", "646-555-7723"],
        must_keep=["Ticket #48213", "Unable to reset password", "Status: Open"],
    ),
    Case(
        "en_academic_abstract_no_pii", "English", "academic abstract", "none",
        "This paper presents a novel approach to gradient-based "
        "optimization in non-convex settings, demonstrating improved "
        "convergence rates on a suite of benchmark datasets compared to "
        "existing first-order methods.",
        must_keep=["gradient-based optimization", "convergence rates"],
    ),

    # ---------- Spanish ----------
    Case(
        "es_business_email", "Spanish", "email", "medium",
        "Hola equipo,\n\n"
        "Por favor contacten a Maria Garcia (maria.garcia@empresa.es, "
        "+34 612 345 678) antes del viernes. Su oficina esta en Madrid.\n\n"
        "Saludos",
        must_redact=["maria.garcia@empresa.es"],
        must_keep=["Saludos", "viernes"],
    ),
    Case(
        "es_news_no_pii", "Spanish", "news article", "none",
        "El gobierno anuncio nuevas medidas economicas para reducir la "
        "inflacion durante el proximo trimestre, segun fuentes oficiales.",
        must_keep=["gobierno", "inflacion", "trimestre"],
    ),

    # ---------- French ----------
    Case(
        "fr_business_letter", "French", "letter", "medium",
        "Bonjour,\n\n"
        "Merci de contacter Pierre Dubois a pierre.dubois@societe.fr ou "
        "au 06 12 34 56 78 pour toute question concernant le contrat.\n\n"
        "Cordialement",
        must_redact=["pierre.dubois@societe.fr"],
        must_keep=["Cordialement", "contrat"],
    ),
    Case(
        "fr_recipe_no_pii", "French", "recipe", "none",
        "Faites revenir les oignons dans l'huile d'olive pendant cinq "
        "minutes, puis ajoutez l'ail et laissez mijoter a feu doux.",
        must_keep=["oignons", "huile d'olive", "feu doux"],
    ),

    # ---------- German ----------
    Case(
        "de_official_letter", "German", "official letter", "medium",
        "Sehr geehrte Damen und Herren,\n\n"
        "Bitte wenden Sie sich an Herrn Klaus Mueller unter "
        "klaus.mueller@firma.de oder 030 12345678 bezueglich Ihrer "
        "Anfrage.\n\n"
        "Mit freundlichen Gruessen",
        must_redact=["klaus.mueller@firma.de"],
        must_keep=["Anfrage", "Mit freundlichen"],
    ),
    Case(
        "de_product_no_pii", "German", "product description", "none",
        "Dieses Produkt besteht aus recyceltem Aluminium und ist fuer den "
        "industriellen Einsatz bei Temperaturen bis zu 200 Grad geeignet.",
        must_keep=["Aluminium", "industriellen", "Temperaturen"],
    ),

    # ---------- Italian ----------
    Case(
        "it_business_email", "Italian", "email", "medium",
        "Ciao,\n\n"
        "Per favore contatta Giulia Romano a giulia.romano@azienda.it o "
        "al numero 340 123 4567 prima di venerdi. Il suo ufficio e a "
        "Milano.\n\nSaluti",
        must_redact=["giulia.romano@azienda.it"],
        must_keep=["Saluti", "venerdi"],
    ),
    Case(
        "it_recipe_no_pii", "Italian", "recipe", "none",
        "Fate soffriggere la cipolla nell'olio d'oliva per cinque minuti, "
        "poi aggiungete l'aglio e lasciate cuocere a fuoco lento.",
        must_keep=["cipolla", "olio d'oliva", "fuoco lento"],
    ),

    # ---------- Portuguese ----------
    Case(
        "pt_business_email", "Portuguese", "email", "medium",
        "Ola equipe,\n\n"
        "Por favor contatem Ana Souza (ana.souza@empresa.com.br, "
        "+55 11 91234-5678) antes de sexta-feira. O escritorio dela fica "
        "em Sao Paulo.\n\nAtenciosamente",
        must_redact=["ana.souza@empresa.com.br"],
        must_keep=["Atenciosamente", "sexta-feira"],
    ),
    Case(
        "pt_news_no_pii", "Portuguese", "news article", "none",
        "O governo anunciou novas medidas economicas para reduzir a "
        "inflacao durante o proximo trimestre, segundo fontes oficiais.",
        must_keep=["governo", "inflacao", "trimestre"],
    ),

    # ---------- Dutch ----------
    Case(
        "nl_business_email", "Dutch", "email", "medium",
        "Hallo team,\n\n"
        "Neem contact op met Sanne de Vries via sanne.devries@bedrijf.nl "
        "of 06 12345678 voor vrijdag. Haar kantoor is in Amsterdam.\n\n"
        "Met vriendelijke groet",
        must_redact=["sanne.devries@bedrijf.nl"],
        must_keep=["Met vriendelijke groet", "vrijdag"],
    ),
    Case(
        "nl_product_no_pii", "Dutch", "product description", "none",
        "Dit product is gemaakt van gerecycled aluminium en geschikt "
        "voor industrieel gebruik bij temperaturen tot 200 graden.",
        must_keep=["aluminium", "industrieel", "temperaturen"],
    ),

    # ---------- Polish ----------
    Case(
        "pl_business_email", "Polish", "email", "medium",
        "Czesc zespole,\n\n"
        "Prosze skontaktowac sie z Anna Kowalska pod adresem "
        "anna.kowalska@firma.pl lub numerem 512 345 678 przed piatkiem.\n\n"
        "Pozdrawiam",
        must_redact=["anna.kowalska@firma.pl"],
        must_keep=["Pozdrawiam", "piatkiem"],
    ),
    Case(
        "pl_news_no_pii", "Polish", "news article", "none",
        "Rzad oglosil nowe srodki gospodarcze majace na celu ograniczenie "
        "inflacji w nadchodzacym kwartale, wedlug oficjalnych zrodel.",
        must_keep=["Rzad", "inflacji", "kwartale"],
    ),

    # ---------- Swedish ----------
    Case(
        "sv_business_email", "Swedish", "email", "medium",
        "Hej teamet,\n\n"
        "Vanligen kontakta Erik Lindqvist pa erik.lindqvist@foretag.se "
        "eller 070-123 45 67 fore fredag. Hans kontor ligger i "
        "Stockholm.\n\nMed vanlig halsning",
        must_redact=["erik.lindqvist@foretag.se"],
        must_keep=["Med vanlig halsning", "fredag"],
    ),

    # ---------- Turkish ----------
    Case(
        "tr_business_email", "Turkish", "email", "medium",
        "Merhaba ekip,\n\n"
        "Lutfen Ayse Yildiz ile ayse.yildiz@sirket.com.tr veya "
        "0532 123 45 67 uzerinden cuma gunune kadar iletisime gecin. "
        "Ofisi Istanbul'da.\n\nSaygilarimla",
        must_redact=["ayse.yildiz@sirket.com.tr"],
        must_keep=["Saygilarimla", "Istanbul"],
    ),

    # ---------- Vietnamese ----------
    Case(
        "vi_business_email", "Vietnamese", "email", "medium",
        "Chao nhom,\n\n"
        "Vui long lien he Nguyen Van An qua email "
        "nguyen.van.an@congty.vn hoac 090 123 4567 truoc thu Sau.\n\n"
        "Tran trong",
        must_redact=["nguyen.van.an@congty.vn"],
        must_keep=["Tran trong"],
    ),

    # ---------- Russian (Cyrillic) ----------
    Case(
        "ru_business_email", "Russian", "email", "medium",
        "Здравствуйте,\n\n"
        "Пожалуйста, свяжитесь с Иваном Петровым по адресу "
        "ivan.petrov@company.ru или по телефону +7 916 123-45-67 до "
        "пятницы.\n\nС уважением",
        must_redact=["ivan.petrov@company.ru"],
        must_keep=["С уважением"],
    ),
    Case(
        "ru_news_no_pii", "Russian", "news article", "none",
        "Правительство объявило о новых экономических мерах для "
        "снижения инфляции в следующем квартале, согласно официальным "
        "источникам.",
        must_keep=["Правительство", "инфляции"],
    ),

    # ---------- Korean ----------
    Case(
        "ko_business_card", "Korean", "business card", "medium",
        "이름: 김민준\n"
        "이메일: minjun.kim@example.co.kr\n"
        "전화번호: 010-1234-5678\n"
        "주소: 서울특별시 강남구",
        must_redact=["minjun.kim@example.co.kr"],
    ),
    Case(
        "ko_paragraph_no_pii", "Korean", "general text", "none",
        "오늘 날씨가 정말 좋아서 산책하기에 딱 좋습니다.",
        must_keep=["날씨"],
    ),

    # ---------- Hindi (Devanagari) ----------
    Case(
        "hi_business_email", "Hindi", "email", "medium",
        "नमस्ते टीम,\n\n"
        "कृपया राहुल शर्मा से संपर्क करें: rahul.sharma@company.in "
        "या 98765 43210 पर शुक्रवार से पहले।\n\n"
        "धन्यवाद",
        must_redact=["rahul.sharma@company.in"],
        must_keep=["धन्यवाद"],
    ),

    # ---------- Thai ----------
    Case(
        "th_contact_card", "Thai", "contact card", "medium",
        "ชื่อ: สมชาย ใจดี\n"
        "อีเมล: somchai.jaidee@example.co.th\n"
        "โทรศัพท์: 081-234-5678",
        must_redact=["somchai.jaidee@example.co.th"],
    ),

    # ---------- Chinese (Simplified) ----------
    Case(
        "zh_business_card", "Chinese (Simplified)", "business card", "medium",
        "姓名：李雷\n"
        "邮箱：li.lei@example.com.cn\n"
        "电话：138-0013-8000\n"
        "地址：北京市朝阳区",
        must_redact=["li.lei@example.com.cn"],
    ),
    Case(
        "zh_paragraph_no_pii", "Chinese (Simplified)", "general text", "none",
        "今天天气非常好，适合出去散步。",
        must_keep=["天气"],
    ),

    # ---------- Arabic (RTL) ----------
    Case(
        "ar_email", "Arabic", "email", "medium",
        "مرحبا،\n"
        "يرجى التواصل مع "
        "أحمد خالد عبر "
        "ahmed.khaled@example.com أو الهاتف "
        "0501234567",
        must_redact=["ahmed.khaled@example.com"],
    ),

    # ---------- Japanese ----------
    Case(
        "ja_contact", "Japanese", "contact card", "medium",
        "お問い合わせは以下まで：\n"
        "メール：tanaka.taro@example.co.jp\n"
        "電話：090-1234-5678",
        must_redact=["tanaka.taro@example.co.jp"],
    ),

    # ---------- Mixed-language / edge cases ----------
    Case(
        "mixed_multilingual", "English + Spanish", "meeting notes", "medium",
        "The meeting notes: 'Gracias, Juan Perez' was heard at the close. "
        "Contact juan.perez@example.com or 555-234-9981 for the recording.",
        must_redact=["juan.perez@example.com", "555-234-9981"],
        must_keep=["meeting notes", "recording"],
    ),
    Case(
        "en_low_density_needle_in_haystack", "English", "long report excerpt", "low",
        "Quarterly performance across all regions exceeded expectations "
        "this cycle, driven largely by strong demand in emerging markets "
        "and disciplined cost management across manufacturing operations. "
        "Leadership remains cautiously optimistic heading into next "
        "quarter, though supply chain volatility remains a risk factor "
        "worth monitoring closely. For internal escalations only, contact "
        "compliance-officer@bigcorp-internal.com. The board will reconvene "
        "in six weeks to reassess capital allocation priorities across "
        "the newly restructured business units.",
        must_redact=["compliance-officer@bigcorp-internal.com"],
        must_keep=["Quarterly performance", "capital allocation", "board"],
    ),

    # ---------- Banking/customer-support phrasing ----------
    # Inspired by Microsoft presidio-research's synthetic sentence templates
    # (MIT licensed, see tools/reference/NOTICE.md) - filled in with our own
    # invented values. Stress-tests CREDIT_CARD/IBAN/PHONE detection in
    # realistic conversational phrasing rather than form-field formatting.
    Case(
        "en_support_card_lost", "English", "customer support chat", "medium",
        "I have lost my card 4111 1111 1111 1111. Could you please block "
        "my credit card ASAP? My name is Rebecca Holt.",
        must_redact=["4111 1111 1111 1111", "Rebecca Holt"],
        must_keep=["Could you please block", "ASAP"],
    ),
    Case(
        "en_support_iban_transfer", "English", "customer support chat", "medium",
        "Are there any charges applied for money transfer from "
        "GB29 NWBK 6016 1331 9268 19 to other bank accounts?",
        must_redact=["GB29 NWBK 6016 1331 9268 19"],
        must_keep=["money transfer", "other bank accounts"],
    ),
    Case(
        "en_support_phone_update", "English", "customer support chat", "low",
        "I have done an online order but didn't get any message on my "
        "registered 415-555-0199. Could you please look into it?",
        must_redact=["415-555-0199"],
        must_keep=["online order", "look into it"],
    ),
    Case(
        "en_support_address_update", "English", "customer support chat", "medium",
        # "billing address" sits inside the ADDRESS rule's intentional
        # bounded context window right next to the real street address -
        # expected, not a leak.
        "Please update the billing address with 42 Maple Terrace, Denver, "
        "CO for this card: 4111 1111 1111 1111",
        must_redact=["4111 1111 1111 1111"],
    ),
    Case(
        "es_support_card_lost", "Spanish", "customer support chat", "medium",
        "He perdido mi tarjeta 4111 1111 1111 1111. ¿Podrian bloquearla "
        "urgentemente? Mi nombre es Roberto Nunez.",
        must_redact=["4111 1111 1111 1111"],
    ),
    Case(
        "fr_support_iban_transfer", "French", "customer support chat", "medium",
        "Y a-t-il des frais pour un virement depuis "
        "FR76 3000 6000 0112 3456 7890 189 vers un autre compte bancaire?",
        # "compte bancaire" gets misread as ORGANIZATION - the known
        # English-NER-on-French-text limitation, not a new bug.
        must_redact=["FR76 3000 6000 0112 3456 7890 189"],
        must_keep=["virement"],
    ),
]


def run() -> int:
    issues = 0
    by_density: dict[str, list[str]] = {}

    for case in CASES:
        result = scrub(case.text, use_ner=True)
        redacted = result.text

        missed = [s for s in case.must_redact if s in redacted]
        over_redacted = [s for s in case.must_keep if s not in redacted]

        status = "OK"
        if missed or over_redacted:
            status = "ISSUES"
            issues += 1
            by_density.setdefault(case.density, []).append(case.id)

        print(f"=== [{status}] {case.id} ({case.language} / {case.doc_type} / {case.density}) ===")
        print(f"counts: {result.counts}")
        if missed:
            print(f"  MISSED (should have been redacted): {missed}")
        if over_redacted:
            print(f"  OVER-REDACTED (should have survived): {over_redacted}")
        print()

    languages = sorted({c.language for c in CASES})
    doc_types = sorted({c.doc_type for c in CASES})
    print(f"{len(CASES)} cases across {len(languages)} languages and {len(doc_types)} document types.")
    print(f"Languages: {', '.join(languages)}")
    print(f"Document types: {', '.join(doc_types)}")
    print(f"{issues} cases with issues.")
    if by_density:
        print(f"Issues by density: {by_density}")
    return issues


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
