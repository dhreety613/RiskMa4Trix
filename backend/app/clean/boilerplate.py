"""Flags risks that are boilerplate - wording so generic that most
filers include something nearly identical (the standard "forward-
looking statements" preamble, "we face intense competition," generic
pandemic language, etc). These aren't wrong, they're just not evidence
of anything company-specific, so the matrix hides them by default
(is_generic) behind a toggle rather than deleting them.

generic_score = fraction of OTHER companies in the DB that have at
least one risk within GENERIC_SIMILARITY_THRESHOLD of this one. This is
a real cross-company IDF-style signal, not a hardcoded phrase list - it
only gets more accurate as more companies are ingested (CLAUDE.md
caveat: with very few companies in the DB, a risk shared by just 2-3 of
them can look "generic" even if it's actually a real, narrow industry
risk - see docs/METHODOLOGY.md limitations once written).
"""

import numpy as np
from sqlalchemy.orm import Session

from app.extract.classifier import _normalize
from app.models import Risk

GENERIC_SIMILARITY_THRESHOLD = 0.85
IS_GENERIC_THRESHOLD = 0.5


def compute_boilerplate_scores(db: Session) -> int:
    """Recomputes generic_score/is_generic for every active risk across
    the WHOLE DB (genericity is inherently cross-company, not per-filing).
    Returns the number of risks updated.
    """
    risks = db.query(Risk).filter(Risk.status == "active").all()
    risks_with_embeddings = [r for r in risks if r.embedding_row]
    if len(risks_with_embeddings) < 2:
        return 0

    company_ids = np.array([r.company_id for r in risks_with_embeddings])
    all_companies = set(company_ids.tolist())
    if len(all_companies) < 2:
        # Genericity is meaningless with only one company in the DB -
        # everything would trivially score 0 (no "other" companies to
        # compare against). Leave scores untouched rather than writing
        # a misleading 0.0 for "not enough data yet".
        return 0

    vectors = _normalize(
        np.array([r.embedding_row.embedding for r in risks_with_embeddings], dtype=np.float32)
    )
    similarities = vectors @ vectors.T

    for i, risk in enumerate(risks_with_embeddings):
        own_company = company_ids[i]
        matches = (similarities[i] >= GENERIC_SIMILARITY_THRESHOLD) & (company_ids != own_company)
        matching_companies = set(company_ids[matches].tolist())
        other_companies = all_companies - {own_company}

        generic_score = len(matching_companies) / len(other_companies) if other_companies else 0.0
        risk.generic_score = generic_score
        risk.is_generic = generic_score >= IS_GENERIC_THRESHOLD

    db.flush()
    return len(risks_with_embeddings)
