import math

import numpy as np

from app.clean.dedupe import dedupe_risks_for_filing
from app.models import Company, Filing, Risk, RiskEmbedding

EMBED_DIM = 384


def _unit_vector(cos_sim_to_e1: float) -> np.ndarray:
    """A unit vector in the span of the first two axes with an EXACT
    cosine similarity to e1 (the first basis vector) - lets tests set
    up precise similarity values instead of guessing with real
    embeddings.
    """
    v = np.zeros(EMBED_DIM, dtype=np.float32)
    v[0] = cos_sim_to_e1
    v[1] = math.sqrt(max(0.0, 1.0 - cos_sim_to_e1**2))
    return v


def _make_company_and_filing(db) -> tuple[Company, Filing]:
    import datetime

    company = Company(ticker="TEST", cik="0000000000", name="Test Co")
    db.add(company)
    db.flush()
    filing = Filing(
        company_id=company.id,
        accession="0000000000-99-000001",
        form_type="10-K",
        fiscal_year=2025,
        filed_date=datetime.date(2025, 1, 1),
        url="https://example.com",
    )
    db.add(filing)
    db.flush()
    return company, filing


def _make_risk(db, filing: Filing, text: str, position_idx: int, vector: np.ndarray) -> Risk:
    risk = Risk(
        filing_id=filing.id,
        company_id=filing.company_id,
        title=text[:40],
        text=text,
        position_idx=position_idx,
        status="active",
    )
    db.add(risk)
    db.flush()
    db.add(RiskEmbedding(risk_id=risk.id, embedding=vector))
    db.flush()
    return risk


def test_near_duplicate_risks_merge_keeping_the_longest(db):
    _, filing = _make_company_and_filing(db)

    short = _make_risk(db, filing, "We face competition.", 0, _unit_vector(1.0))
    long_text = "We face intense and sustained competition in our markets."
    long = _make_risk(db, filing, long_text, 1, _unit_vector(0.95))

    merged = dedupe_risks_for_filing(db, filing)

    db.refresh(short)
    db.refresh(long)
    assert merged == 1
    assert long.status == "active"
    assert long.merged_count == 2
    assert short.status == "merged"


def test_dissimilar_risks_are_not_merged(db):
    _, filing = _make_company_and_filing(db)

    risk_a = _make_risk(db, filing, "We face competition.", 0, _unit_vector(1.0))
    fx_text = "We are exposed to foreign exchange risk."
    risk_b = _make_risk(db, filing, fx_text, 1, _unit_vector(0.0))

    merged = dedupe_risks_for_filing(db, filing)

    db.refresh(risk_a)
    db.refresh(risk_b)
    assert merged == 0
    assert risk_a.status == "active"
    assert risk_b.status == "active"


def test_single_risk_is_a_no_op(db):
    _, filing = _make_company_and_filing(db)
    _make_risk(db, filing, "Only one risk here.", 0, _unit_vector(1.0))

    assert dedupe_risks_for_filing(db, filing) == 0
