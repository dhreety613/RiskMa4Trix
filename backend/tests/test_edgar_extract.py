from app.ingest.edgar import extract_sections

# Mimics the real failure mode found against a live AAPL filing: a table
# of contents lists item+title pairs close together, and prose elsewhere
# cross-references "Item 1A" / "Item 7" without restating the title. A
# naive "last occurrence of the item number" extractor grabs the
# cross-reference instead of the real section.
SAMPLE_10K = """
TABLE OF CONTENTS
Item 1A. Risk Factors 9
Item 1B. Unresolved Staff Comments 20
Item 2. Properties 20
Item 7. Management's Discussion and Analysis of Financial Condition 25
Item 7A. Quantitative and Qualitative Disclosures About Market Risk 40
Item 8. Financial Statements 41

Item 1. Business
We make things.

Item 1A. Risk Factors
Our business faces many risks including supply chain disruption and
foreign currency exposure, as described further below. """ + ("Risk prose. " * 500) + """

Item 1B. Unresolved Staff Comments
None.

Item 2. Properties
We own buildings.

Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations
Revenue grew. See Item 1A of this Form 10-K for risk discussion. """ + ("MDA prose. " * 300) + """

Item 7A. Quantitative and Qualitative Disclosures About Market Risk
We are exposed to interest rate risk. """ + ("Market risk prose. " * 200) + """

Item 8. Financial Statements
See attached.
"""


def test_extracts_real_body_not_toc_or_cross_reference():
    sections = extract_sections(SAMPLE_10K)

    assert sections["item1a_text"].startswith("Item 1A. Risk Factors")
    assert "supply chain disruption" in sections["item1a_text"]
    assert "Item 1B" not in sections["item1a_text"]

    assert sections["item7_text"].startswith("Item 7. Management's Discussion")
    assert "Revenue grew" in sections["item7_text"]
    assert "Item 7A" not in sections["item7_text"]

    assert sections["item7a_text"].startswith("Item 7A. Quantitative")
    assert "interest rate risk" in sections["item7a_text"]
    assert "Item 8" not in sections["item7a_text"]


def test_missing_section_returns_empty_string():
    sections = extract_sections("Item 1. Business\nNothing else here.")
    assert sections["item1a_text"] == ""
    assert sections["item7_text"] == ""
    assert sections["item7a_text"] == ""
