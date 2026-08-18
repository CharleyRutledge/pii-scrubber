import json

from pii_scrubber.extractors import extract_text


def test_extract_txt(tmp_path):
    p = tmp_path / "doc.txt"
    p.write_text("hello world", encoding="utf-8")
    assert extract_text(p) == "hello world"


def test_extract_csv(tmp_path):
    p = tmp_path / "doc.csv"
    p.write_text("name,email\nJane,jane@example.com\n", encoding="utf-8")
    text = extract_text(p)
    assert "jane@example.com" in text


def test_extract_json(tmp_path):
    p = tmp_path / "doc.json"
    p.write_text(json.dumps({"user": {"email": "jane@example.com", "age": 30}}), encoding="utf-8")
    text = extract_text(p)
    assert "jane@example.com" in text


def test_unsupported_suffix_raises(tmp_path):
    p = tmp_path / "doc.xyz"
    p.write_text("data", encoding="utf-8")
    try:
        extract_text(p)
        assert False, "expected ValueError"
    except ValueError:
        pass
