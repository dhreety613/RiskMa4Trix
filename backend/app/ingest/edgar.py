"""SEC EDGAR ingestion: ticker -> CIK, list of 10-Ks, and Item 1A / 7 / 7A
text extraction from the primary filing document.

Deliberately NOT using the `sec_edgar_downloader` package (what the old
reference repo used) - it downloads whole submission text files with no
structure. This talks to the same two JSON APIs SEC actually documents
(company_tickers.json + the submissions/XBRL APIs), which is both lighter
and gives us real fiscal-year/accession metadata to key rows on.
"""

import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup

from app.ingest.http import fetch_json, fetch_text

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

_ticker_to_cik: dict[str, str] | None = None
_ticker_to_name: dict[str, str] | None = None


def _load_ticker_map() -> None:
    global _ticker_to_cik, _ticker_to_name
    if _ticker_to_cik is not None:
        return
    data = fetch_json(TICKERS_URL)
    _ticker_to_cik = {}
    _ticker_to_name = {}
    for row in data.values():
        ticker = row["ticker"].upper()
        _ticker_to_cik[ticker] = f"{row['cik_str']:010d}"
        _ticker_to_name[ticker] = row["title"]


def get_cik_for_ticker(ticker: str) -> str | None:
    _load_ticker_map()
    return _ticker_to_cik.get(ticker.upper())


def get_company_name(ticker: str) -> str | None:
    _load_ticker_map()
    return _ticker_to_name.get(ticker.upper())


@dataclass
class FilingRef:
    accession: str  # dashed, e.g. "0000320193-23-000106"
    form_type: str
    filed_date: date
    primary_document: str
    fiscal_year: int


def list_10k_filings(cik: str, years_back: int = 5) -> list[FilingRef]:
    """Most recent 10-Ks for a CIK, newest first, within `years_back` years."""
    data = fetch_json(SUBMISSIONS_URL.format(cik=cik))
    recent = data["filings"]["recent"]

    cutoff_year = date.today().year - years_back
    out: list[FilingRef] = []

    for form, accession, filed, primary_doc, report_date in zip(
        recent["form"],
        recent["accessionNumber"],
        recent["filingDate"],
        recent["primaryDocument"],
        recent.get("reportDate", recent["filingDate"]),
        strict=True,
    ):
        if form != "10-K":
            continue
        filed_date = date.fromisoformat(filed)
        if filed_date.year < cutoff_year:
            continue
        fiscal_year = int((report_date or filed)[:4])
        out.append(
            FilingRef(
                accession=accession,
                form_type=form,
                filed_date=filed_date,
                primary_document=primary_doc,
                fiscal_year=fiscal_year,
            )
        )

    out.sort(key=lambda f: f.filed_date, reverse=True)
    return out


def filing_document_url(cik: str, filing: FilingRef) -> str:
    accession_nodash = filing.accession.replace("-", "")
    cik_int = str(int(cik))
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
        f"{accession_nodash}/{filing.primary_document}"
    )


def fetch_filing_text(cik: str, filing: FilingRef) -> str:
    """Download the primary document and strip it to plain text."""
    url = filing_document_url(cik, filing)
    raw = fetch_text(url)
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


# Item headers we care about. "item 1a" alone is unreliable as a header
# marker: filings constantly cross-reference other items in prose ("as
# described in Item 1A of this Form 10-K..."), and naively taking the
# textually-last occurrence picks up one of those instead of the real
# section. Real headers are reliably followed by their canonical title
# (that's just how 10-K structure works) - cross-references almost never
# restate the full title right after the item number. So: only count an
# occurrence as a header candidate if the title follows shortly after,
# then among candidates for a given item, pick whichever one produces the
# LONGEST section before the next candidate header - the real body runs
# for thousands of characters, while a table-of-contents entry is only a
# few dozen characters from the next TOC entry.
_ITEM_PATTERN = re.compile(r"item\s+(1a|1b|7a|1|2|7|8)\b[.:]?\s*", re.IGNORECASE)

_ITEM_TITLES = {
    "1a": r"risk\s+factors",
    "1b": r"unresolved\s+staff\s+comments",
    "2": r"propert(?:y|ies)",
    "7": r"management.?s\s+discussion\s+and\s+analysis",
    "7a": r"quantitative\s+and\s+qualitative\s+disclosures",
    "8": r"financial\s+statements",
}

_TITLE_LOOKAHEAD = 40


def _header_candidates(text: str) -> dict[str, list[int]]:
    candidates: dict[str, list[int]] = {k: [] for k in _ITEM_TITLES}
    for match in _ITEM_PATTERN.finditer(text):
        item = match.group(1).lower()
        title_pattern = _ITEM_TITLES.get(item)
        if not title_pattern:
            continue
        following = text[match.end() : match.end() + _TITLE_LOOKAHEAD]
        if re.match(title_pattern, following, re.IGNORECASE):
            candidates[item].append(match.start())
    return candidates


def _best_section(
    candidates: dict[str, list[int]], start_key: str, end_keys: list[str], text_len: int
) -> tuple[int, int] | None:
    starts = candidates.get(start_key, [])
    if not starts:
        return None

    end_positions = sorted(p for k in end_keys for p in candidates.get(k, []))

    best: tuple[int, int] | None = None
    for start in starts:
        end_candidates = [p for p in end_positions if p > start]
        end = end_candidates[0] if end_candidates else text_len
        if best is None or (end - start) > (best[1] - best[0]):
            best = (start, end)
    return best


def extract_sections(full_text: str) -> dict[str, str]:
    """Item 1A (Risk Factors), Item 7 (MD&A), Item 7A (market risk)."""
    candidates = _header_candidates(full_text)

    specs = {
        "item1a_text": ("1a", ["1b", "2"]),
        "item7_text": ("7", ["7a", "8"]),
        "item7a_text": ("7a", ["8"]),
    }

    out: dict[str, str] = {}
    for field, (start_key, end_keys) in specs.items():
        span = _best_section(candidates, start_key, end_keys, len(full_text))
        out[field] = full_text[span[0] : span[1]].strip() if span else ""
    return out
