"""End-to-end tests through the actual CLI surface (subprocess), covering
the real path a user takes: run `pii-scrubber scrub`/`redact` against a
real file on disk and check the real file/stdout it produces - as opposed
to the unit tests elsewhere that call library functions directly.
"""

import json
import subprocess
import sys


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
