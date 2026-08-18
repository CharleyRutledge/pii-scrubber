"""Minimal HTML text/tag splitting, shared by extraction and redaction.

Avoids a full HTML parser dependency: splits raw markup into alternating
tag and text segments so PII detection/redaction only ever touches visible
text, never tag markup or script/style content.
"""

import re

_TAG_OR_TEXT = re.compile(r"(<[^>]*>)")
_SCRIPT_OR_STYLE_OPEN = re.compile(r"^<\s*(script|style)\b", re.IGNORECASE)
_SCRIPT_OR_STYLE_CLOSE = re.compile(r"^<\s*/\s*(script|style)\b", re.IGNORECASE)


def split_html_segments(html: str) -> list[tuple[bool, str]]:
    """Split HTML into (is_tag, segment) pairs. Text inside <script>/<style>
    is marked as tag-like (is_tag=True) so callers skip it.
    """
    pieces = _TAG_OR_TEXT.split(html)
    segments: list[tuple[bool, str]] = []
    in_skip_block = False

    for piece in pieces:
        if not piece:
            continue
        is_tag = piece.startswith("<") and piece.endswith(">")
        if is_tag:
            if _SCRIPT_OR_STYLE_OPEN.match(piece):
                in_skip_block = True
            elif _SCRIPT_OR_STYLE_CLOSE.match(piece):
                in_skip_block = False
            segments.append((True, piece))
        else:
            segments.append((in_skip_block, piece))

    return segments


def extract_html_text(html: str) -> str:
    return "".join(seg for is_tag, seg in split_html_segments(html) if not is_tag)
