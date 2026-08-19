from pii_scrubber.mrz import find_passport_matches
from pii_scrubber.core import scrub

# The official ICAO 9303 published worked example (Part 4, App A) - not a
# real person's passport, used throughout the industry as the canonical
# test vector for MRZ parsers.
_ICAO_LINE1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
_ICAO_LINE2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
_ICAO_MRZ = f"{_ICAO_LINE1}\n{_ICAO_LINE2}"


def test_detects_valid_icao_example():
    matches = find_passport_matches(_ICAO_MRZ)
    assert len(matches) == 1
    assert matches[0].label == "PASSPORT_MRZ"


def test_rejects_tampered_passport_number_check_digit():
    bad_line2 = _ICAO_LINE2[:9] + "7" + _ICAO_LINE2[10:]
    assert find_passport_matches(f"{_ICAO_LINE1}\n{bad_line2}") == []


def test_rejects_tampered_composite_check_digit():
    bad_line2 = _ICAO_LINE2[:-1] + ("1" if _ICAO_LINE2[-1] != "1" else "2")
    assert find_passport_matches(f"{_ICAO_LINE1}\n{bad_line2}") == []


def test_rejects_random_44_char_lines():
    assert find_passport_matches("A" * 44 + "\n" + "B" * 44) == []


def test_rejects_normal_prose():
    text = (
        "This is a perfectly ordinary paragraph of text that happens to be "
        "long enough to wrap across a couple of lines in a real document."
    )
    assert find_passport_matches(text) == []


def test_ignores_lines_of_wrong_length():
    # One line 44 chars, the other not - must not partial-match.
    assert find_passport_matches(f"{_ICAO_LINE1}\nshort line") == []


def test_scrub_redacts_mrz_found_in_a_larger_document():
    text = (
        "Photocopy of passport for visa application.\n\n"
        f"{_ICAO_MRZ}\n\n"
        "Please process by end of week."
    )
    result = scrub(text, use_ner=False)
    assert "L898902C3" not in result.text
    assert "[PASSPORT_MRZ]" in result.text
    assert result.counts["PASSPORT_MRZ"] == 1
