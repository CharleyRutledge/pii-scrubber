"""Runtime environment checks - currently just "can spaCy's NER actually
load here". Separate from core.py because this is about the *environment*
(security policy, missing model, etc.), not the scrubbing logic itself.
"""

import sys
from dataclasses import dataclass


@dataclass
class NerCheckResult:
    ok: bool
    detail: str
    blocked_by_app_control: bool = False


# Windows Security's own protocol handler for its pages. This one isn't
# officially documented by Microsoft, but is stable across Win10/11 and is
# the only way to deep-link straight to the Smart App Control page instead
# of dropping the user on the Windows Security home screen.
_SMART_APP_CONTROL_URI = "windowsdefender://smartappcontrol"


def check_ner_available() -> NerCheckResult:
    """Try to actually load the spaCy model used for NER, the same way
    core.py does. Returns why it failed, if it did, so the CLI can tell
    the difference between "not installed" and "blocked by OS policy".
    """
    try:
        import spacy

        spacy.load("en_core_web_sm")
    except ImportError as exc:
        message = str(exc)
        blocked = "Application Control policy" in message
        return NerCheckResult(ok=False, detail=message, blocked_by_app_control=blocked)
    except OSError as exc:
        # Model not downloaded - `python -m spacy download en_core_web_sm`
        return NerCheckResult(ok=False, detail=str(exc), blocked_by_app_control=False)
    return NerCheckResult(ok=True, detail="spaCy NER model loaded fine.")


def open_smart_app_control_settings() -> bool:
    """Launch the Windows Security "Smart App Control" settings page.

    Returns False (and does nothing) on non-Windows platforms, since the
    setting only exists on Windows 11.
    """
    if sys.platform != "win32":
        return False
    import os

    os.startfile(_SMART_APP_CONTROL_URI)  # noqa: S606 - a Windows Settings URI, not a file path
    return True


def open_code_integrity_event_log() -> bool:
    """Launch Event Viewer directly at the CodeIntegrity operational log,
    where the exact blocking policy + file hash for an Application Control
    block is recorded.

    Uses os.startfile (ShellExecute) rather than subprocess.Popen
    (CreateProcess): eventvwr.exe's manifest requires elevation, and
    CreateProcess can't trigger the UAC prompt for that - it fails with
    OSError: [WinError 740] The requested operation requires elevation.
    ShellExecute handles the elevation prompt correctly.
    """
    if sys.platform != "win32":
        return False
    import os

    os.startfile(  # noqa: S606 - launching a known system tool, not a file path
        "eventvwr.exe",
        arguments="/c:Microsoft-Windows-CodeIntegrity/Operational",
    )
    return True
