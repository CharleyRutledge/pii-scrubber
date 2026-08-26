"""Local-only file storage for the interactive menu: uploaded source files
and scrub/redact outputs both live under one folder in the user's home
directory, never sent anywhere over the network - just a convenience so
files used through `pii-scrubber menu` land somewhere predictable instead
of scattered wherever the original path happened to be.
"""

import shutil
from pathlib import Path

WORKSPACE_DIR = Path.home() / ".pii-scrubber"
UPLOADS_DIR = WORKSPACE_DIR / "uploads"
OUTPUTS_DIR = WORKSPACE_DIR / "outputs"


def ensure_workspace() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def _dedupe(path: Path) -> Path:
    """If `path` already exists, append " (1)", " (2)", ... before the
    suffix until a free name is found - never silently overwrites a
    previous upload/output.
    """
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 1
    while True:
        candidate = path.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def import_file(source: str | Path) -> Path:
    """Copy an external file into the local uploads folder and return its
    new path. The original filename is kept (deduped if already present).
    """
    ensure_workspace()
    source = Path(source)
    dest = _dedupe(UPLOADS_DIR / source.name)
    shutil.copy2(source, dest)
    return dest


def output_path_for(original: str | Path, label: str, suffix: str | None = None) -> Path:
    """Build a deduped path in the local outputs folder named
    "<original stem>_<label><suffix>", e.g. "invoice_redacted.pdf" or
    "invoice_scrubbed.txt".
    """
    ensure_workspace()
    original = Path(original)
    ext = suffix if suffix is not None else original.suffix
    return _dedupe(OUTPUTS_DIR / f"{original.stem}_{label}{ext}")


def list_workspace_files() -> tuple[list[Path], list[Path]]:
    """Return (uploads, outputs) currently stored, newest first."""
    ensure_workspace()

    def _sorted(folder: Path) -> list[Path]:
        return sorted(folder.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

    return _sorted(UPLOADS_DIR), _sorted(OUTPUTS_DIR)
