from pii_scrubber.ner import find_ner_matches


def test_allcaps_name_recognized_via_casing_normalization():
    matches = find_ner_matches("MR CHARLEY RUTLEDGE lives near LIMERICK.")
    labels = {m.label for m in matches}
    assert "PERSON" in labels or any("CHARLEY" in m.text for m in matches)


def test_common_tech_terms_not_flagged_as_pii():
    # Regression: found by testing against a real technical resume, where a
    # dense skills list of framework/tool names got massively over-redacted
    # (25 PERSON + 17 ORGANIZATION matches on one document) because these
    # capitalized, proper-noun-shaped words look like names to a generic
    # NER model. See src/pii_scrubber/nonpii_terms.py.
    text = (
        "Skills: Docker, Git, JSON, jQuery, Node.js, Jira, HTML5, XML, "
        "GraphQL, TypeScript, MongoDB, Kubernetes."
    )
    matches = find_ner_matches(text)
    flagged_texts = {m.text.strip() for m in matches}

    for term in ["Docker", "Git", "JSON", "jQuery", "Node.js", "Jira", "HTML5"]:
        assert term not in flagged_texts, f"{term!r} should not be flagged as PII"


def test_real_name_still_detected_alongside_tech_terms():
    text = "Contact John Carter regarding the Docker and Kubernetes migration."
    matches = find_ner_matches(text)
    assert any(m.label == "PERSON" and "Carter" in m.text for m in matches)
