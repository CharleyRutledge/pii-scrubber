"""Cross-platform "open this file so the user can inspect it" - used by
redact_file(..., open_after=True) / the CLI's --open flag to launch the
redacted file for the user to check immediately.

On Windows this shows the native "How do you want to open this file?"
chooser (rundll32 shell32.dll,OpenAs_RunDLL) rather than silently
launching whatever app is set as the default - the user asked to pick the
app each time rather than have one chosen for them. macOS/Linux don't
have a scriptable equivalent of that dialog without extra dependencies,
so they still launch the OS default app.
"""

import subprocess
import sys
from pathlib import Path


def open_with_default_app(path: str | Path) -> None:
    path = Path(path)
    if sys.platform == "win32":
        subprocess.run(
            ["rundll32.exe", "shell32.dll,OpenAs_RunDLL", str(path)], check=True
        )
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=True)
    else:
        subprocess.run(["xdg-open", str(path)], check=True)
