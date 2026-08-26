"""Tests the platform-dispatch logic in open_file.py without ever actually
launching a real application - subprocess.run / os.startfile are
monkeypatched so these are safe to run anywhere, including CI.
"""

import sys

import pytest

from pii_scrubber.open_file import open_with_default_app


def test_windows_shows_open_with_chooser(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    calls = []
    monkeypatch.setattr(
        "subprocess.run", lambda args, **kw: calls.append(args) or _FakeResult()
    )

    target = tmp_path / "doc.txt"
    target.write_text("x", encoding="utf-8")
    open_with_default_app(target)

    assert calls == [["rundll32.exe", "shell32.dll,OpenAs_RunDLL", str(target)]]


def test_macos_uses_open_command(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    calls = []
    monkeypatch.setattr(
        "subprocess.run", lambda args, **kw: calls.append(args) or _FakeResult()
    )

    target = tmp_path / "doc.txt"
    open_with_default_app(target)

    assert calls == [["open", str(target)]]


def test_linux_uses_xdg_open(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    calls = []
    monkeypatch.setattr(
        "subprocess.run", lambda args, **kw: calls.append(args) or _FakeResult()
    )

    target = tmp_path / "doc.txt"
    open_with_default_app(target)

    assert calls == [["xdg-open", str(target)]]


class _FakeResult:
    returncode = 0
