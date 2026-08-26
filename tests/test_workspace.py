from pii_scrubber import workspace


def _patch_workspace(monkeypatch, tmp_path):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    monkeypatch.setattr(workspace, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(workspace, "OUTPUTS_DIR", outputs)
    return uploads, outputs


def test_import_file_copies_into_uploads_dir(monkeypatch, tmp_path):
    uploads, _ = _patch_workspace(monkeypatch, tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    dest = workspace.import_file(source)

    assert dest == uploads / "source.txt"
    assert dest.read_text(encoding="utf-8") == "hello"


def test_import_file_dedupes_existing_name(monkeypatch, tmp_path):
    uploads, _ = _patch_workspace(monkeypatch, tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    first = workspace.import_file(source)
    second = workspace.import_file(source)

    assert first != second
    assert first.name == "source.txt"
    assert second.name == "source (1).txt"


def test_output_path_for_uses_label_and_dedupes(monkeypatch, tmp_path):
    outputs_dir_holder = _patch_workspace(monkeypatch, tmp_path)[1]
    original = tmp_path / "invoice.pdf"
    original.write_text("x", encoding="utf-8")

    first = workspace.output_path_for(original, "redacted")
    first.write_text("redacted copy", encoding="utf-8")
    second = workspace.output_path_for(original, "redacted")

    assert first == outputs_dir_holder / "invoice_redacted.pdf"
    assert second == outputs_dir_holder / "invoice_redacted (1).pdf"


def test_output_path_for_overrides_extension(monkeypatch, tmp_path):
    _patch_workspace(monkeypatch, tmp_path)
    original = tmp_path / "invoice.pdf"

    result = workspace.output_path_for(original, "scrubbed", ".txt")

    assert result.name == "invoice_scrubbed.txt"


def test_list_workspace_files_newest_first(monkeypatch, tmp_path):
    uploads, outputs = _patch_workspace(monkeypatch, tmp_path)
    uploads.mkdir(parents=True)
    outputs.mkdir(parents=True)

    older = uploads / "older.txt"
    older.write_text("a", encoding="utf-8")
    newer = uploads / "newer.txt"
    newer.write_text("b", encoding="utf-8")
    import os
    import time

    now = time.time()
    os.utime(older, (now - 100, now - 100))
    os.utime(newer, (now, now))

    found_uploads, found_outputs = workspace.list_workspace_files()

    assert found_uploads == [newer, older]
    assert found_outputs == []
