from app.extract.splitter import split_risk_paragraphs
from app.ingest.edgar import BOLD_MARK

BOLD_SAMPLE = (
    f"Item 1A.{BOLD_MARK}Risk Factors{BOLD_MARK}\n"
    f"{BOLD_MARK}Macroeconomic and Industry Risks{BOLD_MARK}\n"
    f"{BOLD_MARK}We face intense competition in highly competitive markets.{BOLD_MARK}\n"
    + ("Competition prose. " * 20)
    + f"\n{BOLD_MARK}Our supply chain depends on a small number of manufacturing "
    f"partners.{BOLD_MARK}\n"
    + ("Supply chain prose. " * 20)
    + f"\n{BOLD_MARK}We are exposed to risks from litigation and legal proceedings.{BOLD_MARK}\n"
    + ("Litigation prose. " * 20)
)

NO_BOLD_SAMPLE = "\n".join(
    [
        "Intro line, short.",
        "",
        "We face intense competition in highly competitive markets. " * 10,
        "",
        "short",
        "",
        "Our supply chain depends on a small number of manufacturing partners. " * 10,
    ]
)


def test_splits_on_bold_lead_sentences_not_group_headers():
    risks = split_risk_paragraphs(BOLD_SAMPLE)

    assert len(risks) == 3
    assert risks[0].text.startswith("We face intense competition")
    assert risks[1].text.startswith("Our supply chain depends")
    assert risks[2].text.startswith("We are exposed to risks from litigation")
    # Group headers like "Macroeconomic and Industry Risks" (no trailing
    # period) must never become their own risk block.
    assert all("Macroeconomic and Industry Risks" not in r.text for r in risks)


def test_position_idx_is_sequential():
    risks = split_risk_paragraphs(BOLD_SAMPLE)
    assert [r.position_idx for r in risks] == [0, 1, 2]


def test_falls_back_to_blank_line_split_without_bold_markers():
    risks = split_risk_paragraphs(NO_BOLD_SAMPLE)

    assert len(risks) == 2
    assert "intense competition" in risks[0].text
    assert "supply chain" in risks[1].text
    # The short filler lines ("Intro line, short.", "short") must be
    # dropped, not treated as risk paragraphs of their own.
    assert all(len(r.text) > 100 for r in risks)


def test_empty_input_returns_no_risks():
    assert split_risk_paragraphs("") == []
