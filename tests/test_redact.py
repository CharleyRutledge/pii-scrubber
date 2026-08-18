import json

import docx

from pii_scrubber import redact_file


def test_redact_txt(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("Email jane.doe@example.com now.", encoding="utf-8")

    out = redact_file(src, use_ner=False)

    assert out == tmp_path / "doc_redacted.txt"
    assert "[EMAIL]" in out.read_text(encoding="utf-8")
    assert "jane.doe@example.com" not in out.read_text(encoding="utf-8")


def test_redact_txt_custom_output(tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("Call 555-123-4567.", encoding="utf-8")
    dest = tmp_path / "custom.txt"

    out = redact_file(src, output_path=dest, use_ner=False)

    assert out == dest
    assert "[PHONE]" in dest.read_text(encoding="utf-8")


def test_redact_csv_preserves_structure(tmp_path):
    src = tmp_path / "doc.csv"
    src.write_text("name,email\nJane,jane@example.com\n", encoding="utf-8")

    out = redact_file(src, use_ner=False)
    content = out.read_text(encoding="utf-8")

    assert "name,email" in content
    assert "jane@example.com" not in content
    assert "[EMAIL]" in content


def test_redact_json_preserves_keys(tmp_path):
    src = tmp_path / "doc.json"
    src.write_text(
        json.dumps({"user": {"email": "jane@example.com", "age": 30}}),
        encoding="utf-8",
    )

    out = redact_file(src, use_ner=False)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["user"]["age"] == 30
    assert data["user"]["email"] == "[EMAIL]"


def test_redact_docx_preserves_paragraph_structure(tmp_path):
    src = tmp_path / "doc.docx"
    document = docx.Document()
    document.add_paragraph("Contact jane.doe@example.com for details.")
    document.add_paragraph("This paragraph has no PII.")
    document.save(str(src))

    out = redact_file(src, use_ner=False)
    result = docx.Document(str(out))

    assert len(result.paragraphs) == 2
    assert "[EMAIL]" in result.paragraphs[0].text
    assert "jane.doe@example.com" not in result.paragraphs[0].text
    assert result.paragraphs[1].text == "This paragraph has no PII."
