"""End-to-end tests through the actual CLI surface (subprocess), covering
the real path a user takes: run `pii-scrubber scrub`/`redact` against a
real file on disk and check the real file/stdout it produces - as opposed
to the unit tests elsewhere that call library functions directly.
"""

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pii_scrubber.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_help_lists_both_commands(tmp_path):
    result = _run_cli("--help", cwd=tmp_path)
    assert result.returncode == 0
    assert "scrub" in result.stdout
    assert "redact" in result.stdout
    assert "doctor" in result.stdout


def test_cli_scrub_prints_redacted_text_and_counts(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("Email jane.doe@example.com or call 555-123-4567.", encoding="utf-8")

    result = _run_cli("scrub", "doc.txt", cwd=tmp_path)

    assert result.returncode == 0
    assert "[EMAIL]" in result.stdout
    assert "[PHONE]" in result.stdout
    assert "jane.doe@example.com" not in result.stdout
    assert "EMAIL: 1" in result.stderr
    assert "PHONE: 1" in result.stderr


def test_cli_scrub_no_ner_flag_skips_person_detection(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("MR CHARLEY RUTLEDGE, contact jane@example.com.", encoding="utf-8")

    with_ner = _run_cli("scrub", "doc.txt", cwd=tmp_path)
    without_ner = _run_cli("scrub", "--no-ner", "doc.txt", cwd=tmp_path)

    assert "[EMAIL]" in with_ner.stdout
    assert "[EMAIL]" in without_ner.stdout
    # The all-caps titled-name regex rule still fires without NER, since
    # it's a regex rule, not spaCy - both should redact the name.
    assert "CHARLEY RUTLEDGE" not in with_ner.stdout
    assert "CHARLEY RUTLEDGE" not in without_ner.stdout


def test_cli_redact_writes_format_preserved_copy(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")

    result = _run_cli("redact", "doc.txt", cwd=tmp_path)

    assert result.returncode == 0
    out_path = tmp_path / "doc_redacted.txt"
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "[EMAIL]" in content
    assert "jane.doe@example.com" not in content


def test_cli_redact_custom_output_path(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("SSN: 123-45-6789", encoding="utf-8")

    result = _run_cli("redact", "doc.txt", "-o", "clean.txt", cwd=tmp_path)

    assert result.returncode == 0
    out_path = tmp_path / "clean.txt"
    assert out_path.exists()
    assert "[SSN]" in out_path.read_text(encoding="utf-8")


def test_cli_redact_json_preserves_structure_end_to_end(tmp_path):
    src = tmp_path / "record.json"
    src.write_text(
        json.dumps({"user": {"email": "jane@example.com", "age": 41}}),
        encoding="utf-8",
    )

    result = _run_cli("redact", "record.json", cwd=tmp_path)

    assert result.returncode == 0
    out_path = tmp_path / "record_redacted.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["user"]["email"] == "[EMAIL]"
    assert data["user"]["age"] == 41


def test_cli_scrub_missing_file_fails_cleanly(tmp_path):
    result = _run_cli("scrub", "does_not_exist.txt", cwd=tmp_path)
    assert result.returncode != 0


def test_cli_redact_open_flag_launches_the_output_file(tmp_path, monkeypatch):
    # Run in-process (not via subprocess like the tests above) and mock the
    # actual OS launch, since CI runs headless and has no default file
    # handler (no xdg-open) to safely exercise for real.
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    opened = []
    monkeypatch.setattr("pii_scrubber.redact.open_with_default_app", opened.append)

    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["redact", str(src), "--open"])

    assert result.exit_code == 0
    assert opened == [tmp_path / "doc_redacted.txt"]


def test_cli_redact_without_open_flag_does_not_launch(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    opened = []
    monkeypatch.setattr("pii_scrubber.redact.open_with_default_app", opened.append)

    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["redact", str(src)])

    assert result.exit_code == 0
    assert opened == []


def test_cli_scrub_output_flag_writes_redacted_text(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")

    result = _run_cli("scrub", "doc.txt", "-o", "clean.txt", cwd=tmp_path)

    assert result.returncode == 0
    out_path = tmp_path / "clean.txt"
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "[EMAIL]" in content
    assert "jane.doe@example.com" not in content


def test_cli_scrub_open_flag_writes_temp_file_and_launches_it(tmp_path, monkeypatch):
    # Run in-process (not via subprocess) and mock the actual OS launch,
    # since CI runs headless and has no default file handler to safely
    # exercise for real.
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    opened = []
    monkeypatch.setattr("pii_scrubber.cli.open_with_default_app", opened.append)

    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["scrub", str(src), "--open"])

    assert result.exit_code == 0
    assert len(opened) == 1
    opened_path = opened[0]
    assert opened_path.exists()
    content = opened_path.read_text(encoding="utf-8")
    assert "[EMAIL]" in content
    opened_path.unlink()  # clean up the temp file this test created


def test_cli_scrub_open_flag_writes_to_explicit_output_path(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    opened = []
    monkeypatch.setattr("pii_scrubber.cli.open_with_default_app", opened.append)

    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")
    dest = tmp_path / "clean.txt"

    runner = CliRunner()
    result = runner.invoke(main, ["scrub", str(src), "-o", str(dest), "--open"])

    assert result.exit_code == 0
    assert opened == [dest]
    assert "[EMAIL]" in dest.read_text(encoding="utf-8")


def test_cli_scrub_without_open_or_output_writes_no_file(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    opened = []
    monkeypatch.setattr("pii_scrubber.cli.open_with_default_app", opened.append)

    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")

    before = set(tmp_path.iterdir())
    runner = CliRunner()
    result = runner.invoke(main, ["scrub", str(src)])
    after = set(tmp_path.iterdir())

    assert result.exit_code == 0
    assert opened == []
    assert before == after


def test_cli_doctor_reports_ok_when_ner_loads(monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main
    from pii_scrubber.diagnostics import NerCheckResult

    monkeypatch.setattr(
        "pii_scrubber.cli.check_ner_available",
        lambda: NerCheckResult(ok=True, detail="spaCy NER model loaded fine."),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])

    assert result.exit_code == 0
    assert "OK" in result.output


def test_cli_doctor_offers_to_open_settings_when_app_control_blocked(monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main
    from pii_scrubber.diagnostics import NerCheckResult

    monkeypatch.setattr(
        "pii_scrubber.cli.check_ner_available",
        lambda: NerCheckResult(
            ok=False,
            detail="DLL load failed while importing senter: An Application "
            "Control policy has blocked this file.",
            blocked_by_app_control=True,
        ),
    )
    monkeypatch.setattr("pii_scrubber.cli.sys.platform", "win32")
    opened_settings = []
    opened_log = []
    monkeypatch.setattr(
        "pii_scrubber.cli.open_smart_app_control_settings",
        lambda: opened_settings.append(True),
    )
    monkeypatch.setattr(
        "pii_scrubber.cli.open_code_integrity_event_log",
        lambda: opened_log.append(True),
    )

    runner = CliRunner()
    # Confirm "yes" to opening settings, "no" to opening the event log.
    result = runner.invoke(main, ["doctor"], input="y\nn\n")

    assert result.exit_code == 0
    assert opened_settings == [True]
    assert opened_log == []
    assert "Smart App Control" in result.output


def test_cli_doctor_says_no_when_declined(monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main
    from pii_scrubber.diagnostics import NerCheckResult

    monkeypatch.setattr(
        "pii_scrubber.cli.check_ner_available",
        lambda: NerCheckResult(
            ok=False,
            detail="An Application Control policy has blocked this file.",
            blocked_by_app_control=True,
        ),
    )
    monkeypatch.setattr("pii_scrubber.cli.sys.platform", "win32")
    opened = []
    monkeypatch.setattr(
        "pii_scrubber.cli.open_smart_app_control_settings",
        lambda: opened.append(True),
    )
    monkeypatch.setattr(
        "pii_scrubber.cli.open_code_integrity_event_log",
        lambda: opened.append(True),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["doctor"], input="n\nn\n")

    assert result.exit_code == 0
    assert opened == []


def test_cli_upload_copies_into_local_workspace(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    src = tmp_path / "doc.txt"
    src.write_text("hello", encoding="utf-8")

    dest = tmp_path / "uploads" / "doc.txt"
    monkeypatch.setattr("pii_scrubber.cli.import_file", lambda path: dest)

    runner = CliRunner()
    result = runner.invoke(main, ["upload", str(src)])

    assert result.exit_code == 0
    assert "Uploaded to" in result.output


def test_cli_list_shows_uploads_and_outputs(monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    monkeypatch.setattr(
        "pii_scrubber.cli.list_workspace_files",
        lambda: ([Path("uploads/a.txt")], [Path("outputs/a_redacted.txt")]),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    assert "a.txt" in result.output
    assert "a_redacted.txt" in result.output


def test_cli_menu_exits_immediately_on_choice_zero():
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["menu"], input="0\n")

    assert result.exit_code == 0
    assert "PII - Scrubber" in result.output


def test_cli_bare_invocation_launches_menu():
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    runner = CliRunner()
    result = runner.invoke(main, [], input="0\n")

    assert result.exit_code == 0
    assert "PII - Scrubber" in result.output


def test_cli_menu_upload_then_exit(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    src = tmp_path / "doc.txt"
    src.write_text("hello", encoding="utf-8")
    uploaded = tmp_path / "uploaded_doc.txt"
    monkeypatch.setattr("pii_scrubber.cli.import_file", lambda path: uploaded)

    runner = CliRunner()
    result = runner.invoke(main, ["menu"], input=f"1\n{src}\n0\n")

    assert result.exit_code == 0
    assert "Uploaded to" in result.output


def test_cli_menu_scrub_flow(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")

    monkeypatch.setattr("pii_scrubber.cli.list_workspace_files", lambda: ([], []))
    monkeypatch.setattr(
        "pii_scrubber.cli.output_path_for",
        lambda original, label, suffix=None: tmp_path / f"{original.stem}_{label}.txt",
    )

    runner = CliRunner()
    # 2 = scrub, path, use NER? -> n, save? -> n (skip actually saving/opening)
    result = runner.invoke(main, ["menu"], input=f"2\n{src}\nn\nn\n0\n")

    assert result.exit_code == 0
    assert "[EMAIL]" in result.output


def test_cli_menu_redact_flow(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main

    src = tmp_path / "doc.txt"
    src.write_text("Contact jane.doe@example.com now.", encoding="utf-8")
    out_path = tmp_path / "doc_redacted.txt"

    monkeypatch.setattr("pii_scrubber.cli.list_workspace_files", lambda: ([], []))
    monkeypatch.setattr(
        "pii_scrubber.cli.output_path_for", lambda original, label, suffix=None: out_path
    )
    monkeypatch.setattr("pii_scrubber.cli.redact_file", lambda *a, **kw: out_path)

    runner = CliRunner()
    # 3 = redact, path, use NER? -> n, open? -> n
    result = runner.invoke(main, ["menu"], input=f"3\n{src}\nn\nn\n0\n")

    assert result.exit_code == 0
    assert f"Wrote {out_path}" in result.output


def test_cli_doctor_reports_missing_model_without_offering_settings(monkeypatch):
    from click.testing import CliRunner

    from pii_scrubber.cli import main
    from pii_scrubber.diagnostics import NerCheckResult

    monkeypatch.setattr(
        "pii_scrubber.cli.check_ner_available",
        lambda: NerCheckResult(
            ok=False, detail="[E050] Can't find model", blocked_by_app_control=False
        ),
    )

    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])

    assert result.exit_code == 0
    assert "--no-ner" in result.output
    assert "Smart App Control" not in result.output
