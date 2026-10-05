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


# Modern 10-Ks (inline XBRL) almost never use semantic <b>/<strong> tags -
# "bold" is a CSS font-weight on a <span>. Mark those spans with a
# sentinel before flattening to text, so extract/splitter.py can later
# tell a risk factor's bolded lead sentence (which is how 10-Ks actually
# mark the start of each risk - confirmed against a real AAPL filing)
# apart from plain prose, without needing the HTML again.
BOLD_MARK = "\x01"
_BOLD_STYLE = re.compile(r"font-weight:\s*(bold|bolder|[6-9]00)", re.IGNORECASE)


def _mark_bold_spans(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(style=_BOLD_STYLE):
        if not tag.get_text().strip():
            continue
        tag.insert_before(BOLD_MARK)
        tag.insert_after(BOLD_MARK)
    for tag in soup.find_all(["b", "strong"]):
        if not tag.get_text().strip():
            continue
        tag.insert_before(BOLD_MARK)
        tag.insert_after(BOLD_MARK)


def fetch_filing_text(cik: str, filing: FilingRef) -> str:
    """Download the primary document and flatten it to text that keeps
    paragraph breaks and bold-span markers (splitter.py needs both to
    find individual risk factors) instead of collapsing everything to
    one single-spaced line.
    """
    url = filing_document_url(cik, filing)
    raw = fetch_text(url)
    soup = BeautifulSoup(raw, "html.parser")
    _mark_bold_spans(soup)
    text = soup.get_text("\n")
    text = re.sub(r"[ \t]+", " ", text)  # collapse horizontal whitespace only
    text = re.sub(r"[ \n]*\n[ \n]*", "\n", text)  # drop blank/whitespace-only lines
    return text.strip()


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

# Full canonical SEC titles, alphanumeric-only (matched against a
# SQUASHED version of the lookahead window - see _header_candidates).
# Needs the WHOLE real title so the line-break check lands right after
# it: "Management's Discussion and Analysis" alone (missing "of
# Financial Condition and Results of Operations") was getting rejected
# as a false cross-reference since legitimate title text still followed
# it on the same line.
# Lists, not single strings: filers genuinely vary the exact title text
# (e.g. Item 8 as just "Financial Statements" vs the longer "...and
# Supplementary Data"), and the line-break check needs the match to
# reach the true end of whatever title text is actually there - matching
# only a prefix of a longer real title left genuine title text before
# the next line break, which looked exactly like a cross-reference and
# got rejected. Tried longest-first so the fullest real title wins.
_ITEM_TITLES_SQUASHED = {
    "1a": ["riskfactors"],
    "1b": ["unresolvedstaffcomments"],
    "2": ["propert"],  # prefix of both "property" and "properties"
    "7": ["managementsdiscussionandanalysisoffinancialconditionandresultsofoperations"],
    "7a": ["quantitativeandqualitativedisclosuresaboutmarketrisk"],
    "8": ["financialstatementsandsupplementarydata", "financialstatements"],
}

_TITLE_LOOKAHEAD = 120


def _squash_with_mapping(s: str) -> tuple[str, list[int]]:
    """Alphanumeric characters only, lowercased, each paired with its
    index in `s` - lets title matching ignore whitespace/punctuation/
    bold-sentinels entirely (including the ones Microsoft's filing
    renderer puts INSIDE a single word - see _header_candidates) while
    still being able to point back at the real text afterward.
    """
    chars: list[str] = []
    positions: list[int] = []
    for i, ch in enumerate(s):
        if ch.isalnum():
            chars.append(ch.lower())
            positions.append(i)
    return "".join(chars), positions


def _header_candidates(text: str) -> dict[str, list[int]]:
    candidates: dict[str, list[int]] = {k: [] for k in _ITEM_TITLES_SQUASHED}
    for match in _ITEM_PATTERN.finditer(text):
        item = match.group(1).lower()
        targets = _ITEM_TITLES_SQUASHED.get(item)
        if not targets:
            continue

        following_raw = text[match.end() : match.end() + _TITLE_LOOKAHEAD]
        # Squash away whitespace/punctuation/bold-sentinels before
        # matching - some filers wrap a title's text across several
        # adjacent bold spans at arbitrary points, even mid-word
        # (confirmed in a real Microsoft 10-K: "RIS" and "K FACTORS" as
        # two separate bold spans, rendering as "RIS\n\x01\n\x01\nK
        # FACTORS" once flattened - squashed, both read as "riskfactors").
        squashed, positions = _squash_with_mapping(following_raw)

        target = next((t for t in targets if squashed.startswith(t)), None)
        if target is None:
            continue

        # A real header is a short bolded run-in heading on its own line
        # - immediately after the title there's always a line break (or
        # the bold-sentinel closing it, or end of text), checked against
        # the ORIGINAL (unsquashed) text so this boundary signal survives
        # the squashing above. A prose cross-reference that happens to
        # restate the title verbatim keeps going on the SAME line
        # instead, with or without visible punctuation first - confirmed
        # two different real shapes of this in one NVIDIA 10-K:
        # '...Risk Factors," our Consolidated' (comma) and '...Risk
        # Factors for additional information' (straight into lowercase
        # prose, no punctuation at all). Both must be rejected, or they
        # out-compete the real header under _best_section's "longest
        # span wins" rule - an early false start reaching the same later
        # end boundary as the real header produces a LONGER, not
        # shorter, fake span.
        title_end_orig = positions[len(target) - 1] + 1
        after_title = following_raw[title_end_orig : title_end_orig + 6]
        # A trailing period/colon right after the title ("Risk
        # Factors.\nThe following discussion...", confirmed in a real
        # JPMorgan 10-K) is still a real header - only skip ONE such
        # punctuation char (plus surrounding spaces/nbsp) before the
        # line-break check, so a cross-reference's own punctuation
        # further into its sentence doesn't also get skipped past.
        after_title = after_title.lstrip(" \xa0")
        if after_title[:1] in (".", ":"):
            after_title = after_title[1:].lstrip(" \xa0")
        if after_title and after_title[0] not in ("\n", BOLD_MARK):
            continue
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
