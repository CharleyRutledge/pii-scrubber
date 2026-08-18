from pii_scrubber.rules import find_regex_matches


def test_email_detected():
    matches = find_regex_matches("Contact me at jane.doe@example.com please.")
    labels = [m.label for m in matches]
    assert "EMAIL" in labels


def test_phone_detected():
    matches = find_regex_matches("Call 555-123-4567 tomorrow.")
    assert any(m.label == "PHONE" for m in matches)


def test_ssn_detected():
    matches = find_regex_matches("SSN: 123-45-6789")
    assert any(m.label == "SSN" for m in matches)


def test_credit_card_luhn_filters_invalid():
    # Valid Visa test number (passes Luhn)
    valid = find_regex_matches("Card: 4111 1111 1111 1111")
    assert any(m.label == "CREDIT_CARD" for m in valid)

    # Random 16-digit string that fails Luhn should not match
    invalid = find_regex_matches("Ref number: 1234 5678 9012 3459")
    assert not any(m.label == "CREDIT_CARD" for m in invalid)


def test_ip_address_detected():
    matches = find_regex_matches("Server at 192.168.1.10 is down.")
    assert any(m.label == "IP_ADDRESS" for m in matches)


def test_address_suffix_words_dont_match_as_common_lowercase_english():
    # Regression: "Close", "Court", "Park", "Row", "Way", "Place" are common
    # English words as well as street suffixes. Matching them
    # case-insensitively previously let a phrase like "at the close of the
    # meeting" trigger a false ADDRESS match wide enough to swallow real PII
    # (an email/phone) sitting nearby in the same sentence.
    text = (
        "Contact jane.doe@example.com or 555-123-4567 after the close of "
        "the meeting; let's park the discussion and pick a way forward."
    )
    matches = find_regex_matches(text)

    assert not any(m.label == "ADDRESS" for m in matches)
    assert any(m.label == "EMAIL" and m.text == "jane.doe@example.com" for m in matches)
    assert any(m.label == "PHONE" for m in matches)


def test_address_suffix_still_matches_title_case_real_address():
    matches = find_regex_matches("47 Quins Cottages, Rossbrien Road")
    assert any(m.label == "ADDRESS" for m in matches)


def test_iban_detected_with_conventional_spacing():
    # Regression: found via a real invoice PDF - IBANs are conventionally
    # displayed grouped in 4s with spaces (ISO 13616), not as one unbroken
    # string, and the original regex silently missed the spaced form.
    spaced = find_regex_matches("IBAN: GB29 NWBK 6016 1331 9268 19")
    assert any(m.label == "IBAN" and m.text == "GB29 NWBK 6016 1331 9268 19" for m in spaced)

    compact = find_regex_matches("IBAN: DE89370400440532013000")
    assert any(m.label == "IBAN" and m.text == "DE89370400440532013000" for m in compact)
