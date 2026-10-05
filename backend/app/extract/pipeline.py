"""Orchestrates extraction for one filing: split Item 1A -> classify
each paragraph -> title -> embed -> persist. Also classifies news items
against the same taxonomy and links them to risks (news as evidence for
scoring/probability.py later, and as a signal for emerging categories
not yet in any 10-K).
"""

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.extract.classifier import classify_text, load_taxonomy
from app.extract.embedder import embed_text, embed_texts
from app.extract.splitter import split_risk_paragraphs
from app.extract.titles import generate_title
from app.models import Company, Filing, NewsItem, NewsRiskLink, Risk, RiskEmbedding, Taxonomy

logger = logging.getLogger(__name__)

# Applied ON TOP OF a same-category requirement (see classify_and_link_news)
# - within-category similarity already runs higher than cross-category, so
# this needs to be stricter than UNCLASSIFIED_THRESHOLD (0.35) to mean
# anything as a second filter.
NEWS_RISK_LINK_THRESHOLD = 0.6


def ensure_taxonomy_seeded(db: Session) -> dict[str, int]:
    """Upserts config_data/taxonomy.yaml into the `taxonomy` table and
    returns {slug: id}. Idempotent AND safe under concurrent callers -
    an atomic INSERT ... ON CONFLICT, not a check-then-insert (which
    raised UniqueViolation when two /companies/{ticker}/ingest requests'
    background tasks both tried to seed the same taxonomy at once).
    """
    categories = load_taxonomy()
    stmt = pg_insert(Taxonomy).values(
        [
            {"slug": c.slug, "name": c.name, "group": c.group, "description": c.description}
            for c in categories
        ]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={"name": stmt.excluded.name, "group": stmt.excluded.group,
              "description": stmt.excluded.description},
    )
    db.execute(stmt)
    db.flush()

    rows = db.query(Taxonomy.slug, Taxonomy.id).filter(
        Taxonomy.slug.in_([c.slug for c in categories])
    ).all()
    return {slug: id_ for slug, id_ in rows}


def extract_risks_for_filing(db: Session, filing: Filing) -> list[Risk]:
    if not filing.item1a_text:
        return []

    slug_to_id = ensure_taxonomy_seeded(db)
    categories = {c.slug: c for c in load_taxonomy()}
    paragraphs = split_risk_paragraphs(filing.item1a_text)

    risks: list[Risk] = []
    for para in paragraphs:
        existing = (
            db.query(Risk)
            .filter(Risk.filing_id == filing.id, Risk.position_idx == para.position_idx)
            .one_or_none()
        )
        if existing is not None:
            risks.append(existing)
            continue

        result = classify_text(para.text)
        category = categories.get(result.category_slug) if result.category_slug else None
        title = generate_title(para.text, category)

        risk = Risk(
            filing_id=filing.id,
            company_id=filing.company_id,
            category_id=slug_to_id.get(result.category_slug) if result.category_slug else None,
            category_confidence=result.confidence,
            title=title,
            text=para.text,
            position_idx=para.position_idx,
            status="active",
        )
        db.add(risk)
        db.flush()  # need risk.id before writing the embedding row

        db.add(RiskEmbedding(risk_id=risk.id, embedding=embed_text(para.text)))
        risks.append(risk)

    db.flush()
    logger.info(f"Extracted {len(risks)} risks for filing {filing.accession}")
    return risks


def extract_for_company(db: Session, company: Company) -> None:
    """Runs extraction for every filing of a company, dedupes within
    each filing, recomputes cross-company boilerplate scores, then
    classifies and links its news. Called right after ingestion so a
    newly-ingested ticker has risks (not just raw filings) to show in
    the matrix.
    """
    from app.clean.boilerplate import compute_boilerplate_scores
    from app.clean.dedupe import dedupe_risks_for_filing

    filings = db.query(Filing).filter(Filing.company_id == company.id).all()
    for filing in filings:
        extract_risks_for_filing(db, filing)
        dedupe_risks_for_filing(db, filing)
    db.commit()

    # Cross-company by nature - a new company changes what counts as
    # "generic" for every OTHER company too, not just this one.
    compute_boilerplate_scores(db)
    db.commit()

    classify_and_link_news(db, company)
    db.commit()


def classify_and_link_news(db: Session, company: Company) -> None:
    slug_to_id = ensure_taxonomy_seeded(db)

    unclassified_news = (
        db.query(NewsItem)
        .filter(NewsItem.company_id == company.id, NewsItem.embedding.is_(None))
        .all()
    )
    if unclassified_news:
        vectors = embed_texts([n.title for n in unclassified_news])
        for item, vector in zip(unclassified_news, vectors, strict=True):
            item.embedding = vector
            result = classify_text(item.title)
            item.category_id = (
                slug_to_id.get(result.category_slug) if result.category_slug else None
            )
        db.flush()

    # Link news to specific risks in the SAME category (per CLAUDE.md's
    # source spec: "category match + embedding similarity above
    # threshold") whose text is also semantically close to the headline.
    # Category match alone isn't a tight enough bar - without it, a
    # generic-sounding headline comes back similar (>0.5 cosine) to most
    # risks regardless of topic, which is useless as evidence for any
    # one specific risk (confirmed: dropping the category filter linked
    # one fairly ordinary day's news to over half of all risk x news
    # pairs across 65 risks and 30 headlines).
    import numpy as np

    from app.extract.classifier import _normalize

    risks_with_embeddings = [
        r for r in db.query(Risk).filter(Risk.company_id == company.id).all() if r.embedding_row
    ]
    if not risks_with_embeddings:
        return

    risks_by_category: dict[int, list[Risk]] = {}
    for risk in risks_with_embeddings:
        if risk.category_id is not None:
            risks_by_category.setdefault(risk.category_id, []).append(risk)

    news_items = db.query(NewsItem).filter(NewsItem.company_id == company.id).all()
    for item in news_items:
        if item.embedding is None or item.category_id is None:
            continue
        candidates = risks_by_category.get(item.category_id, [])
        if not candidates:
            continue

        existing_links = {
            link.risk_id
            for link in db.query(NewsRiskLink).filter(NewsRiskLink.news_id == item.id).all()
        }
        risk_ids = [r.id for r in candidates]
        risk_vectors = _normalize(
            np.array([r.embedding_row.embedding for r in candidates], dtype=np.float32)
        )
        news_vector = _normalize(np.array([item.embedding], dtype=np.float32))[0]
        similarities = risk_vectors @ news_vector

        for risk_id, sim in zip(risk_ids, similarities, strict=True):
            if sim >= NEWS_RISK_LINK_THRESHOLD and risk_id not in existing_links:
                db.add(NewsRiskLink(news_id=item.id, risk_id=risk_id, similarity=float(sim)))
    db.flush()
