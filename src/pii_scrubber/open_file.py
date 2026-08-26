"""Cross-platform "open this file with whatever app the OS has associated
with it" - used by redact_file(..., open_after=True) / the CLI's --open
flag to launch the redacted file for the user to inspect immediately.
"""

import subprocess
import sys
from pathlib import Path


def open_with_default_app(path: str | Path) -> None:
    path = Path(path)
    if sys.platform == "win32":
        import os

        os.startfile(path)  # noqa: S606 - launching a local file the user just created
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=True)
    else:
        subprocess.run(["xdg-open", str(path)], check=True)
