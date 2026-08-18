"""Core scrub API: merges regex + NER matches and redacts text in place."""

from dataclasses import dataclass, field
from pathlib import Path

from .entities import EntityMatch
from .ner import find_ner_matches
from .rules import find_regex_matches


@dataclass
class ScrubResult:
    text: str
    entities: list[EntityMatch] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entities:
            out[e.label] = out.get(e.label, 0) + 1
        return out


def _merge_overlaps(matches: list[EntityMatch]) -> list[EntityMatch]:
    """Sort by start; drop matches fully contained in / overlapping an earlier,
    longer match. Regex rules win over NER on overlap since they're more precise.
    """
    ordered = sorted(matches, key=lambda m: (m.start, -(m.end - m.start), m.source != "regex"))
    kept: list[EntityMatch] = []
    last_end = -1
    for m in ordered:
        if m.start >= last_end:
            kept.append(m)
            last_end = m.end
    return kept


def _redact(text: str, matches: list[EntityMatch]) -> str:
    out = []
    cursor = 0
    for m in matches:
        out.append(text[cursor:m.start])
        out.append(f"[{m.label}]")
        cursor = m.end
    out.append(text[cursor:])
    return "".join(out)


def scrub(
    text: str,
    use_ner: bool = True,
    ner_model: str = "en_core_web_sm",
    ner_labels: set[str] | None = None,
) -> ScrubResult:
    """Scrub PII from a text string, returning redacted text and found entities."""
    matches = find_regex_matches(text)
    if use_ner:
        matches += find_ner_matches(text, model_name=ner_model, labels=ner_labels)

    merged = _merge_overlaps(matches)
    redacted = _redact(text, merged)
    return ScrubResult(text=redacted, entities=merged)


def scrub_file(
    path: str | Path,
    use_ner: bool = True,
    ner_model: str = "en_core_web_sm",
    ner_labels: set[str] | None = None,
) -> ScrubResult:
    """Extract text from a file (.txt/.md/.pdf/.docx/.csv/.json) and scrub it."""
    from .extractors import extract_text

    text = extract_text(path)
    return scrub(text, use_ner=use_ner, ner_model=ner_model, ner_labels=ner_labels)
