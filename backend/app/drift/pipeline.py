"""Runs drift matching across every consecutive pair of filings for a
company, persisting DriftEvent rows. Idempotent: clears existing events
for a (from_filing, to_filing) pair before re-inserting.
"""

from sqlalchemy.orm import Session

from app.drift.matcher import match_filing_risks
from app.models import Company, DriftEvent, Filing, Risk


def _active_risks(db: Session, filing: Filing) -> list[Risk]:
    return db.query(Risk).filter(Risk.filing_id == filing.id, Risk.status == "active").all()


def compute_drift_for_company(db: Session, company: Company) -> int:
    """Returns the number of DriftEvent rows written."""
    filings = (
        db.query(Filing)
        .filter(Filing.company_id == company.id)
        .order_by(Filing.fiscal_year)
        .all()
    )
    if len(filings) < 2:
        return 0

    total = 0
    for prev_filing, curr_filing in zip(filings, filings[1:], strict=False):
        db.query(DriftEvent).filter(
            DriftEvent.from_filing_id == prev_filing.id,
            DriftEvent.to_filing_id == curr_filing.id,
        ).delete()

        prev_risks = _active_risks(db, prev_filing)
        curr_risks = _active_risks(db, curr_filing)
        matches = match_filing_risks(prev_risks, curr_risks)

        for match in matches:
            db.add(
                DriftEvent(
                    company_id=company.id,
                    from_filing_id=prev_filing.id,
                    to_filing_id=curr_filing.id,
                    risk_id=match.curr_risk.id if match.curr_risk else None,
                    prev_risk_id=match.prev_risk.id if match.prev_risk else None,
                    label=match.label,
                    similarity=match.similarity,
                )
            )
            total += 1

    db.flush()
    return total
