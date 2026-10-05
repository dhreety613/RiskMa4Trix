import datetime
import itertools

from app.models import Company, DriftEvent, Filing, NewsItem, NewsRiskLink, Risk
from app.scoring.probability import _load_priors, compute_probability

_ticker_counter = itertools.count(1)


def _make_company_filing_risk(db):
    n = next(_ticker_counter)
    company = Company(ticker=f"PROB{n}", cik=f"000000000{n}", name=f"Prob Co {n}")
    db.add(company)
    db.flush()
    filing = Filing(
        company_id=company.id,
        accession=f"0000000001-99-{n:06d}",
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
        title="A risk",
        text="Some risk text.",
        position_idx=0,
        status="active",
    )
    db.add(risk)
    db.flush()
    return company, filing, risk


def test_posterior_matches_beta_formula_with_no_evidence(db):
    _, _, risk = _make_company_filing_risk(db)

    priors = _load_priors()
    row = priors["cybersecurity"]
    p0, n0 = row["p0"], row["n0"]

    result = compute_probability(db, risk, "cybersecurity")

    assert result.evidence_months == 0
    assert result.drift_pseudo_count == 0
    # No evidence at all -> posterior falls exactly back to the prior.
    expected_alpha = p0 * n0
    expected_beta = (1 - p0) * n0 + 12
    assert abs(result.alpha - expected_alpha) < 1e-9
    assert abs(result.beta - expected_beta) < 1e-9
    assert result.p_lo < result.p_mean < result.p_hi


def test_unknown_category_uses_default_prior(db):
    _, _, risk = _make_company_filing_risk(db)
    result = compute_probability(db, risk, "not_a_real_category")
    assert result.used_default_prior is True


def test_news_evidence_increases_posterior_mean(db):
    company, filing, risk = _make_company_filing_risk(db)

    now = datetime.datetime.utcnow()
    for months_ago in (1, 2, 3):
        news = NewsItem(
            company_id=company.id,
            published_at=now - datetime.timedelta(days=30 * months_ago),
            title=f"News {months_ago}",
            url=f"https://example.com/news/{months_ago}",
        )
        db.add(news)
        db.flush()
        db.add(NewsRiskLink(news_id=news.id, risk_id=risk.id, similarity=0.7))
    db.flush()

    baseline = compute_probability(db, risk, "cybersecurity")
    with_evidence = compute_probability(db, risk, "cybersecurity")

    assert with_evidence.evidence_months == 3
    # Same call signature, but now there IS evidence in the DB - compare
    # against a risk with no linked news to confirm evidence raises P.
    _, _, bare_risk = _make_company_filing_risk(db)
    bare = compute_probability(db, bare_risk, "cybersecurity")
    assert with_evidence.p_mean > bare.p_mean
    assert baseline.p_mean == with_evidence.p_mean  # deterministic given same DB state


def test_drift_new_label_adds_pseudo_count(db):
    company, filing, risk = _make_company_filing_risk(db)
    db.add(
        DriftEvent(
            company_id=company.id,
            from_filing_id=None,
            to_filing_id=filing.id,
            risk_id=risk.id,
            label="new",
        )
    )
    db.flush()

    result = compute_probability(db, risk, "cybersecurity")
    assert result.drift_pseudo_count == 1
