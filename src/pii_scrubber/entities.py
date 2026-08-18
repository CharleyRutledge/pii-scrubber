from dataclasses import dataclass


@dataclass(frozen=True)
class EntityMatch:
    """A single PII span found in text."""

    label: str
    text: str
    start: int
    end: int
    source: str  # "regex" or "ner"

    def __len__(self) -> int:
        return self.end - self.start
