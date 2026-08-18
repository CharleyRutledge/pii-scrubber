from pii_scrubber.core import scrub


def test_scrub_regex_only_no_ner():
    result = scrub("Email jane.doe@example.com or call 555-123-4567.", use_ner=False)
    assert "[EMAIL]" in result.text
    assert "[PHONE]" in result.text
    assert "jane.doe@example.com" not in result.text
    assert result.counts["EMAIL"] == 1
    assert result.counts["PHONE"] == 1


def test_scrub_preserves_non_pii_text():
    result = scrub("The weather is nice today.", use_ner=False)
    assert result.text == "The weather is nice today."
    assert result.entities == []


def test_overlapping_matches_merge_without_duplication():
    # Overlapping SSN-like and phone-like patterns shouldn't double-redact.
    result = scrub("Number: 123-45-6789", use_ner=False)
    assert result.text.count("[SSN]") == 1
