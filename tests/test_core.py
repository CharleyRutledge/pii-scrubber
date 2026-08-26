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


def test_longer_regex_match_wins_over_earlier_starting_shorter_ner_match():
    # Regression: found via a real bank statement payment reference
    # ("Charley rutledge Elizabeth scanlon 47 quins cottages rossbrien
    # road..."). NER's "Charley" PERSON match starts a few characters
    # before the much longer ADDRESS regex match, which only partially
    # overlaps it rather than being fully contained in it. Sorting
    # candidates by start position (the old behavior) kept "Charley"
    # first and then dropped the entire ADDRESS match as "overlapping" -
    # silently leaking the whole address and both surnames. The merge
    # must keep whichever match is longer regardless of which starts
    # first.
    text = (
        "Reference: Charley rutledge Elizabeth scanlon 47 quins cottages "
        "rossbrien road 1024 euro rent"
    )
    result = scrub(text, use_ner=True)
    assert "[ADDRESS]" in result.text
    assert "rutledge" not in result.text.lower()
    assert "cottages" not in result.text.lower()
