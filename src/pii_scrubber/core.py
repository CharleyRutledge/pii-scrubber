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


_ADDRESS_ADJACENT_LABELS = {"ADDRESS", "EIRCODE"}


def _find_adjacent_location_lines(text: str, matches: list[EntityMatch]) -> list[EntityMatch]:
    """A bare place name on its own line inside a postal address block (e.g.
    "LIMERICK" on the line between a street and an Eircode) often has too
    little sentence context for generic NER to recognize as a location.
    Structurally, a short all-caps line directly touching an already-found
    ADDRESS/EIRCODE line is very likely the city/town - catch it here.
    """
    lines = text.splitlines(keepends=True)
    line_starts = []
    cursor = 0
    for line in lines:
        line_starts.append(cursor)
        cursor += len(line)

    def line_index_for(offset: int) -> int:
        for i in range(len(line_starts) - 1, -1, -1):
            if line_starts[i] <= offset:
                return i
        return 0

    covered = [(m.start, m.end) for m in matches]

    def is_covered(start: int, end: int) -> bool:
        return any(s < end and e > start for s, e in covered)

    found: list[EntityMatch] = []
    anchor_line_idxs = {
        line_index_for(m.start) for m in matches if m.label in _ADDRESS_ADJACENT_LABELS
    }

    for anchor_idx in anchor_line_idxs:
        for candidate_idx in (anchor_idx - 1, anchor_idx + 1):
            if candidate_idx < 0 or candidate_idx >= len(lines):
                continue
            raw_line = lines[candidate_idx]
            stripped = raw_line.strip()
            word_count = len(stripped.split())
            if not (0 < len(stripped) <= 30 and 1 <= word_count <= 3):
                continue
            if not stripped.isupper() or not any(c.isalpha() for c in stripped):
                continue

            start = line_starts[candidate_idx] + raw_line.index(stripped)
            end = start + len(stripped)
            if is_covered(start, end):
                continue

            found.append(EntityMatch("LOCATION", stripped, start, end, source="heuristic"))
            covered.append((start, end))

    return found


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
    matches += _find_adjacent_location_lines(text, matches)

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
