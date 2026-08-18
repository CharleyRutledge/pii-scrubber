"""spaCy-based NER detection for free-text PII (names, locations, orgs)."""

from functools import lru_cache

from .entities import EntityMatch

# spaCy entity labels we treat as PII, mapped to our own label names.
_NER_LABEL_MAP = {
    "PERSON": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "ORG": "ORGANIZATION",
    "FAC": "LOCATION",
    "NORP": "AFFILIATION",
}

_DEFAULT_MODEL = "en_core_web_sm"


@lru_cache(maxsize=4)
def _load_model(model_name: str):
    import spacy

    try:
        return spacy.load(model_name)
    except OSError as exc:
        raise RuntimeError(
            f"spaCy model '{model_name}' is not installed. Run:\n"
            f"    python -m spacy download {model_name}"
        ) from exc


def find_ner_matches(
    text: str, model_name: str = _DEFAULT_MODEL, labels: set[str] | None = None
) -> list[EntityMatch]:
    """Run spaCy NER over text and return PII entity matches.

    `labels` restricts output to a subset of our label names (e.g. {"PERSON"});
    defaults to every label in `_NER_LABEL_MAP`.
    """
    nlp = _load_model(model_name)
    doc = nlp(text)

    matches: list[EntityMatch] = []
    for ent in doc.ents:
        our_label = _NER_LABEL_MAP.get(ent.label_)
        if our_label is None:
            continue
        if labels is not None and our_label not in labels:
            continue
        matches.append(
            EntityMatch(our_label, ent.text, ent.start_char, ent.end_char, source="ner")
        )

    return matches
