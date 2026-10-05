"""Deterministically splits a filing's Item 1A text into individual risk
factor paragraphs - no LLM involved (see CLAUDE.md hard rules: extraction
is retrieval/classification-first, never free LLM extraction).

Primary strategy, confirmed against a real AAPL 10-K: each risk factor
starts with a bolded lead sentence (a full sentence ending in "."),
while bolded SECTION GROUP headers ("Business Risks", "Financial Risks")
don't end in a period - that one textual cue is what tells a risk's own
heading apart from a group divider, without needing the HTML again.

Fallback strategy, for filers that don't bold each risk's lead sentence:
split on blank-line paragraph breaks instead, dropping short/boilerplate
lines (typically intro sentences or stray headers).
"""

import re
from dataclasses import dataclass

from app.ingest.edgar import BOLD_MARK

MIN_HEADING_LEN = 15
MIN_FALLBACK_PARAGRAPH_LEN = 120
# Below this many bold-headed candidates, assume this filer doesn't use
# the bold-lead-sentence convention and fall back to paragraph splitting.
MIN_BOLD_CANDIDATES = 3


@dataclass
class RiskParagraph:
    text: str
    position_idx: int
    start_offset: int
    end_offset: int


def _clean(text: str) -> str:
    text = text.replace(BOLD_MARK, "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def _bold_span_positions(text: str) -> list[tuple[int, int]]:
    marks = [i for i, ch in enumerate(text) if ch == BOLD_MARK]
    return [(marks[i] + 1, marks[i + 1]) for i in range(0, len(marks) - 1, 2)]


def _is_risk_heading(span_text: str) -> bool:
    cleaned = span_text.replace("\xa0", " ").strip()
    return len(cleaned) >= MIN_HEADING_LEN and cleaned.endswith(".")


def _split_by_bold_headings(text: str) -> list[RiskParagraph]:
    heading_starts = [
        start for start, end in _bold_span_positions(text) if _is_risk_heading(text[start:end])
    ]
    if len(heading_starts) < MIN_BOLD_CANDIDATES:
        return []

    paragraphs: list[RiskParagraph] = []
    for idx, start in enumerate(heading_starts):
        end = heading_starts[idx + 1] if idx + 1 < len(heading_starts) else len(text)
        cleaned = _clean(text[start:end])
        if cleaned:
            paragraphs.append(
                RiskParagraph(text=cleaned, position_idx=idx, start_offset=start, end_offset=end)
            )
    return paragraphs


def _split_by_blank_lines(text: str) -> list[RiskParagraph]:
    stripped = text.replace(BOLD_MARK, "")
    raw_paragraphs = [p.strip() for p in stripped.split("\n")]

    paragraphs: list[RiskParagraph] = []
    offset = 0
    idx = 0
    for raw in raw_paragraphs:
        start = stripped.find(raw, offset) if raw else offset
        end = start + len(raw)
        offset = end
        cleaned = _clean(raw)
        if len(cleaned) >= MIN_FALLBACK_PARAGRAPH_LEN:
            paragraphs.append(
                RiskParagraph(text=cleaned, position_idx=idx, start_offset=start, end_offset=end)
            )
            idx += 1
    return paragraphs


def split_risk_paragraphs(item1a_text: str) -> list[RiskParagraph]:
    if not item1a_text:
        return []
    return _split_by_bold_headings(item1a_text) or _split_by_blank_lines(item1a_text)
