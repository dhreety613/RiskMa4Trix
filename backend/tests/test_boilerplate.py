import datetime

from app.clean.boilerplate import compute_boilerplate_scores
from app.models import Company, Filing, Risk, RiskEmbedding
from tests.test_dedupe import _unit_vector


def _make_company_filing_risk(db, ticker: str, text: str, vector):
    company = Company(ticker=ticker, cik=f"000000{ticker}", name=f"{ticker} Inc")
    db.add(company)
    db.flush()
    filing = Filing(
        company_id=company.id,
        accession=f"0000000000-99-{ticker}",
        form_type="10-K",
        fiscal_year=2025,
        filed_date=datetime.date(2025, 1, 1),
        url="https://example.com",
    )
    db.add(filing)
    db.flush()
    risk = Risk(
        filing_id=filing.id,
        company_id=company.id,
        title=text[:40],
        text=text,
        position_idx=0,
        status="active",
    )
    db.add(risk)
    db.flush()
    db.add(RiskEmbedding(risk_id=risk.id, embedding=vector))
    db.flush()
    return risk


def test_risk_shared_by_half_of_other_companies_is_generic(db):
    # A and B both have a near-identical boilerplate-style risk; C has
    # something unrelated. For A (and B), the ONE other near-duplicate
    # (the other of A/B) out of TWO other companies (B-or-A, and C)
    # gives exactly the 0.5 generic_score threshold.
    risk_a = _make_company_filing_risk(
        db, "AAAA", "We face intense competition.", _unit_vector(1.0)
    )
    risk_b = _make_company_filing_risk(
        db, "BBBB", "We face intense and sustained competition.", _unit_vector(0.95)
    )
    unrelated_text = "Our factory depends on a single supplier of rare earth metals."
    risk_c = _make_company_filing_risk(db, "CCCC", unrelated_text, _unit_vector(0.0))

    updated = compute_boilerplate_scores(db)

    db.refresh(risk_a)
    db.refresh(risk_b)
    db.refresh(risk_c)

    assert updated == 3
    assert risk_a.is_generic is True
    assert risk_b.is_generic is True
    assert risk_c.is_generic is False
    assert risk_c.generic_score == 0.0


def test_single_company_is_not_scored(db):
    risk = _make_company_filing_risk(db, "SOLO", "We face some risk.", _unit_vector(1.0))

    updated = compute_boilerplate_scores(db)

    db.refresh(risk)
    assert updated == 0
    assert risk.is_generic is False
    assert risk.generic_score is None
