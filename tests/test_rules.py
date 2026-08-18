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
