import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.extract.pipeline import extract_for_company
from app.ingest.pipeline import ingest_company_full
from app.models import Company, Filing
from app.schemas import CompanyOut, FilingOut, IngestAck

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/companies", tags=["companies"])


def _run_ingest_background(ticker: str) -> None:
    db = SessionLocal()
    try:
        company = ingest_company_full(db, ticker)
        extract_for_company(db, company)
    except Exception:
        logger.exception(f"Background ingest failed for {ticker}")
    finally:
        db.close()


@router.post("/{ticker}/ingest", response_model=IngestAck)
def trigger_ingest(
    ticker: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> IngestAck:
    from app.ingest.edgar import get_cik_for_ticker

    if get_cik_for_ticker(ticker) is None:
        raise HTTPException(status_code=404, detail=f"Unknown ticker {ticker!r}")

    background_tasks.add_task(_run_ingest_background, ticker.upper())
    return IngestAck(ticker=ticker.upper(), status="queued")


@router.get("", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)) -> list[Company]:
    return db.query(Company).order_by(Company.ticker).all()


@router.get("/{ticker}", response_model=CompanyOut)
def get_company(ticker: str, db: Session = Depends(get_db)) -> Company:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail=f"{ticker!r} not ingested yet")
    return company


@router.get("/{ticker}/filings", response_model=list[FilingOut])
def list_filings(ticker: str, db: Session = Depends(get_db)) -> list[FilingOut]:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail=f"{ticker!r} not ingested yet")

    filings = (
        db.query(Filing)
        .filter(Filing.company_id == company.id)
        .order_by(Filing.fiscal_year.desc())
        .all()
    )
    return [
        FilingOut(
            id=f.id,
            accession=f.accession,
            form_type=f.form_type,
            fiscal_year=f.fiscal_year,
            filed_date=f.filed_date,
            url=f.url,
            has_item1a=bool(f.item1a_text),
            has_item7=bool(f.item7_text),
            has_item7a=bool(f.item7a_text),
        )
        for f in filings
    ]
