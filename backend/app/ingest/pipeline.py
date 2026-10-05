"""Orchestrates one company's ingestion: EDGAR filings -> financial facts
-> price stats -> news, all upserted so re-running never duplicates rows
(the idempotency rule in CLAUDE.md).
"""

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.ingest import edgar, financials, news, prices
from app.models import Company, Filing, FinancialFact, NewsItem, PriceStat

logger = logging.getLogger(__name__)


class TickerNotFound(Exception):
    pass


def upsert_company(db: Session, ticker: str) -> Company:
    cik = edgar.get_cik_for_ticker(ticker)
    if cik is None:
        raise TickerNotFound(f"No CIK found for ticker {ticker!r}")
    name = edgar.get_company_name(ticker) or ticker

    company = db.query(Company).filter(Company.ticker == ticker.upper()).one_or_none()
    if company is None:
        company = Company(ticker=ticker.upper(), cik=cik, name=name)
        db.add(company)
        db.flush()
    else:
        company.cik = cik
        company.name = name
    return company


def ingest_filings(db: Session, company: Company, years_back: int = 5) -> list[int]:
    """Returns the fiscal years actually ingested (for financials.py)."""
    fiscal_years: list[int] = []
    for fref in edgar.list_10k_filings(company.cik, years_back=years_back):
        existing = (
            db.query(Filing)
            .filter(Filing.company_id == company.id, Filing.accession == fref.accession)
            .one_or_none()
        )
        if existing is not None:
            fiscal_years.append(existing.fiscal_year)
            continue

        try:
            full_text = edgar.fetch_filing_text(company.cik, fref)
        except Exception:
            logger.exception(f"Failed to fetch filing {fref.accession} for {company.ticker}")
            continue
        sections = edgar.extract_sections(full_text)

        filing = Filing(
            company_id=company.id,
            accession=fref.accession,
            form_type=fref.form_type,
            fiscal_year=fref.fiscal_year,
            filed_date=fref.filed_date,
            url=edgar.filing_document_url(company.cik, fref),
            item1a_text=sections["item1a_text"] or None,
            item7_text=sections["item7_text"] or None,
            item7a_text=sections["item7a_text"] or None,
        )
        db.add(filing)
        fiscal_years.append(fref.fiscal_year)

    db.flush()
    return fiscal_years


def ingest_financial_facts(db: Session, company: Company, fiscal_years: list[int]) -> None:
    if not fiscal_years:
        return
    for yf_facts in financials.fetch_financial_facts(company.cik, fiscal_years):
        for metric, value in financials.facts_to_rows(yf_facts).items():
            existing = (
                db.query(FinancialFact)
                .filter(
                    FinancialFact.company_id == company.id,
                    FinancialFact.fiscal_year == yf_facts.fiscal_year,
                    FinancialFact.metric == metric,
                )
                .one_or_none()
            )
            if existing is not None:
                existing.value = value
            else:
                db.add(
                    FinancialFact(
                        company_id=company.id,
                        fiscal_year=yf_facts.fiscal_year,
                        metric=metric,
                        value=value,
                    )
                )
    db.flush()


def ingest_price_stats(db: Session, company: Company) -> None:
    result = prices.compute_price_stats(company.ticker)
    today = date.today()

    existing = (
        db.query(PriceStat)
        .filter(PriceStat.company_id == company.id, PriceStat.as_of == today)
        .one_or_none()
    )
    if existing is not None:
        existing.ann_vol = result.ann_vol
        existing.beta = result.beta
        existing.dd95_1y = result.dd95_1y
        existing.mcap = result.mcap
    else:
        db.add(
            PriceStat(
                company_id=company.id,
                as_of=today,
                ann_vol=result.ann_vol,
                beta=result.beta,
                dd95_1y=result.dd95_1y,
                mcap=result.mcap,
            )
        )
    db.flush()


def ingest_news(db: Session, company: Company) -> None:
    for row in news.fetch_company_news(company.name):
        existing = db.query(NewsItem).filter(NewsItem.url == row.url).one_or_none()
        if existing is not None:
            continue
        db.add(
            NewsItem(
                company_id=company.id,
                published_at=row.published_at,
                title=row.title,
                source=row.source,
                url=row.url,
                snippet=row.snippet,
            )
        )
    db.flush()


def ingest_company_full(db: Session, ticker: str, years_back: int = 5) -> Company:
    company = upsert_company(db, ticker)
    fiscal_years = ingest_filings(db, company, years_back=years_back)
    ingest_financial_facts(db, company, fiscal_years)
    ingest_price_stats(db, company)
    ingest_news(db, company)
    db.commit()
    logger.info(f"Ingested {ticker}: {len(fiscal_years)} filings")
    return company
