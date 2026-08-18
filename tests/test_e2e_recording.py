"""Runs the actual demo recorder (tools/record_demo.py) end-to-end and
verifies it produced a real, valid GIF and a matching walkthrough doc whose
content is the CLI's genuine output — not that a video "looks right", but
that the pipeline that generates our documentation actually runs correctly
and that the PII in the demo fixture was, in fact, redacted.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import record_demo  # noqa: E402


@pytest.fixture(scope="module")
def demo_result(tmp_path_factory):
    # Shared across this file's tests: the recorder spawns several fresh
    # Python subprocesses (each loading spaCy) plus GIF rendering, so it's
    # expensive enough to be worth running once rather than per-test.
    return record_demo.generate(tmp_path_factory.mktemp("demo"))


def test_recorder_produces_valid_multi_frame_gif(demo_result):
    gif_path = demo_result["gif_path"]
    assert gif_path.exists()

    with Image.open(gif_path) as im:
        assert im.n_frames > 1
        assert im.size[0] > 0 and im.size[1] > 0


def test_recorder_doc_reflects_real_redaction(demo_result):
    doc_text = demo_result["doc_path"].read_text(encoding="utf-8")

    # The doc must show the tool actually redacting the fixture's PII —
    # not a hand-written claim that it works.
    assert "[EMAIL]" in doc_text
    assert "[SSN]" in doc_text
    assert "jane.doe@example.com" not in doc_text
    assert "123-45-6789" not in doc_text

    assert "![demo](assets/demo.gif)" in doc_text


def test_recorder_steps_all_succeeded(demo_result):
    for step in demo_result["steps"]:
        assert step.returncode == 0, f"step failed: {step.display_command}\n{step.output}"
