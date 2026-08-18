from pii_scrubber import redact_file, scrub_file


def _write_html(tmp_path):
    src = tmp_path / "cv.html"
    src.write_text(
        "<html><head><style>.x{color:jane.doe@example.com}</style>"
        "<script>var email='jane.doe@example.com';</script></head>"
        "<body><p>Contact jane.doe@example.com or 555-123-4567.</p></body></html>",
        encoding="utf-8",
    )
    return src


def test_scrub_file_ignores_script_and_style(tmp_path):
    src = _write_html(tmp_path)
    result = scrub_file(src, use_ner=False)
    # Only the visible-text occurrence should be redacted/counted.
    assert result.counts["EMAIL"] == 1
    assert result.counts["PHONE"] == 1


def test_redact_html_preserves_tags_and_skips_script_style(tmp_path):
    src = _write_html(tmp_path)
    out = redact_file(src, use_ner=False)
    content = out.read_text(encoding="utf-8")

    assert "<html>" in content
    assert "<p>" in content
    # Script/style content untouched.
    assert "var email='jane.doe@example.com';" in content
    assert ".x{color:jane.doe@example.com}" in content
    # Visible text redacted.
    assert "[EMAIL]" in content
    assert "[PHONE]" in content
    assert "Contact jane.doe@example.com" not in content
