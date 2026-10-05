"""SEC XBRL companyfacts -> the handful of line items the impact model
(scoring/impact.py) actually needs: revenue, an EBITDA proxy, total debt,
cash, and (when disclosed) foreign revenue share. Market cap comes from
yfinance (prices.py) instead - XBRL doesn't carry live market data.

XBRL tagging is inconsistent across filers (one company's revenue is
`Revenues`, another's is `RevenueFromContractWithCustomerExcludingAssessedTax`),
so each metric tries a list of tag candidates in order and takes the first
that has annual (duration ~1yr, form 10-K) data for the fiscal year.
"""

from collections import defaultdict
from dataclasses import dataclass

from app.ingest.http import fetch_json

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Ordered by preference - first tag with usable data for a given fiscal
# year wins. us-gaap namespace only; ifrs-full filers are out of scope.
_TAG_CANDIDATES: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization",
    ],
    "total_debt_current": [
        "DebtCurrent",
        "LongTermDebtCurrent",
    ],
    "total_debt_noncurrent": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
}


@dataclass
class YearFacts:
    fiscal_year: int
    revenue: float | None = None
    ebitda: float | None = None
    total_debt: float | None = None
    cash: float | None = None


def _annual_values_by_year(unit_rows: list[dict], form: str = "10-K") -> dict[int, float]:
    """XBRL duration facts for a tag, keyed by fiscal year (`fy`).

    Filters to ~1-year durations from 10-Ks so we don't pick up quarterly
    (10-Q) facts or balance-sheet instants by mistake for duration tags.
    """
    out: dict[int, float] = {}
    for row in unit_rows:
        if row.get("form") != form or row.get("fp") != "FY":
            continue
        fy = row.get("fy")
        if fy is None:
            continue
        start, end = row.get("start"), row.get("end")
        if start and end:
            days = (_parse_date(end) - _parse_date(start)).days
            if not (300 <= days <= 400):
                continue
        out[fy] = row["val"]
    return out


def _instant_values_by_year(unit_rows: list[dict], form: str = "10-K") -> dict[int, float]:
    """XBRL instant facts (balance-sheet items) keyed by fiscal year."""
    out: dict[int, float] = {}
    for row in unit_rows:
        if row.get("form") != form or row.get("fp") != "FY":
            continue
        fy = row.get("fy")
        if fy is None:
            continue
        out[fy] = row["val"]
    return out


def _parse_date(s: str):
    from datetime import date

    return date.fromisoformat(s)


def _best_tag_series(facts: dict, tags: list[str], instant: bool) -> dict[int, float]:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        tag_data = us_gaap.get(tag)
        if not tag_data:
            continue
        unit_rows = next(iter(tag_data.get("units", {}).values()), [])
        series = (
            _instant_values_by_year(unit_rows) if instant else _annual_values_by_year(unit_rows)
        )
        if series:
            return series
    return {}


def fetch_financial_facts(cik: str, fiscal_years: list[int]) -> list[YearFacts]:
    facts = fetch_json(COMPANYFACTS_URL.format(cik=cik))

    revenue = _best_tag_series(facts, _TAG_CANDIDATES["revenue"], instant=False)
    op_income = _best_tag_series(facts, _TAG_CANDIDATES["operating_income"], instant=False)
    d_and_a = _best_tag_series(facts, _TAG_CANDIDATES["depreciation_amortization"], instant=False)
    debt_current = _best_tag_series(facts, _TAG_CANDIDATES["total_debt_current"], instant=True)
    debt_noncurrent = _best_tag_series(
        facts, _TAG_CANDIDATES["total_debt_noncurrent"], instant=True
    )
    cash = _best_tag_series(facts, _TAG_CANDIDATES["cash"], instant=True)

    out: list[YearFacts] = []
    for fy in fiscal_years:
        ebitda = None
        if fy in op_income:
            ebitda = op_income[fy] + d_and_a.get(fy, 0.0)

        debt = None
        if fy in debt_current or fy in debt_noncurrent:
            debt = debt_current.get(fy, 0.0) + debt_noncurrent.get(fy, 0.0)

        out.append(
            YearFacts(
                fiscal_year=fy,
                revenue=revenue.get(fy),
                ebitda=ebitda,
                total_debt=debt,
                cash=cash.get(fy),
            )
        )
    return out


def facts_to_rows(year_facts: YearFacts) -> dict[str, float]:
    """Flatten a YearFacts into {metric_name: value} for FinancialFact rows,
    dropping metrics that came back empty (XBRL coverage is inconsistent -
    a missing metric is a `pending`/fallback case downstream, not an error).
    """
    row = defaultdict(float)
    for field in ("revenue", "ebitda", "total_debt", "cash"):
        value = getattr(year_facts, field)
        if value is not None:
            row[field] = value
    return dict(row)
