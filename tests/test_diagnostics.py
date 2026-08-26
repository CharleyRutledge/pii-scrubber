import sys

import pytest

from pii_scrubber import diagnostics


def test_check_ner_available_ok(monkeypatch):
    class FakeSpacy:
        @staticmethod
        def load(name):
            return object()

    monkeypatch.setitem(sys.modules, "spacy", FakeSpacy())
    result = diagnostics.check_ner_available()
    assert result.ok
    assert not result.blocked_by_app_control


def test_check_ner_available_detects_app_control_block(monkeypatch):
    class FakeSpacy:
        @staticmethod
        def load(name):
            raise ImportError(
                "DLL load failed while importing senter: An Application "
                "Control policy has blocked this file."
            )

    monkeypatch.setitem(sys.modules, "spacy", FakeSpacy())
    result = diagnostics.check_ner_available()
    assert not result.ok
    assert result.blocked_by_app_control


def test_check_ner_available_missing_model_is_not_app_control(monkeypatch):
    class FakeSpacy:
        @staticmethod
        def load(name):
            raise OSError(f"[E050] Can't find model '{name}'")

    monkeypatch.setitem(sys.modules, "spacy", FakeSpacy())
    result = diagnostics.check_ner_available()
    assert not result.ok
    assert not result.blocked_by_app_control


def test_open_smart_app_control_settings_noop_off_windows(monkeypatch):
    monkeypatch.setattr(diagnostics.sys, "platform", "linux")
    assert diagnostics.open_smart_app_control_settings() is False


def test_open_smart_app_control_settings_launches_uri_on_windows(monkeypatch):
    monkeypatch.setattr(diagnostics.sys, "platform", "win32")
    calls = []
    monkeypatch.setattr(
        "os.startfile", lambda uri: calls.append(uri), raising=False
    )
    assert diagnostics.open_smart_app_control_settings() is True
    assert calls == ["windowsdefender://smartappcontrol"]


def test_open_code_integrity_event_log_noop_off_windows(monkeypatch):
    monkeypatch.setattr(diagnostics.sys, "platform", "linux")
    assert diagnostics.open_code_integrity_event_log() is False


def test_open_code_integrity_event_log_launches_on_windows(monkeypatch):
    monkeypatch.setattr(diagnostics.sys, "platform", "win32")
    calls = []
    monkeypatch.setattr(
        diagnostics.subprocess, "Popen", lambda args: calls.append(args)
    )
    assert diagnostics.open_code_integrity_event_log() is True
    assert calls == [["eventvwr.exe", "/c:Microsoft-Windows-CodeIntegrity/Operational"]]
