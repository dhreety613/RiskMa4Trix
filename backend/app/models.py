"""SQLAlchemy models - mirrors docs/METHODOLOGY.md section on schema.

Every table here maps 1:1 to a step in the pipeline (ingest -> extract ->
clean -> drift -> score -> simulate). See CLAUDE.md for the full pipeline
description.
"""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EMBED_DIM = 384


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    cik: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sic: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    filings: Mapped[list["Filing"]] = relationship(back_populates="company")


class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (UniqueConstraint("company_id", "accession", name="uq_filing_accession"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    accession: Mapped[str] = mapped_column(String(32))
    form_type: Mapped[str] = mapped_column(String(16), default="10-K")
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    filed_date: Mapped[date] = mapped_column(Date)
    url: Mapped[str] = mapped_column(Text)
    item1a_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    item7_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    item7a_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="filings")
    risks: Mapped[list["Risk"]] = relationship(back_populates="filing")


class FinancialFact(Base):
    __tablename__ = "financial_facts"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", "metric", name="uq_fact_metric_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    metric: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="USD")
    source: Mapped[str] = mapped_column(String(32), default="xbrl")


class PriceStat(Base):
    __tablename__ = "price_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date)
    ann_vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    beta: Mapped[float | None] = mapped_column(Float, nullable=True)
    dd95_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    mcap: Mapped[float | None] = mapped_column(Float, nullable=True)


class Taxonomy(Base):
    __tablename__ = "taxonomy"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    group: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("taxonomy.id"), nullable=True)
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    position_idx: Mapped[int] = mapped_column(Integer)
    merged_count: Mapped[int] = mapped_column(Integer, default=1)
    is_generic: Mapped[bool] = mapped_column(Boolean, default=False)
    generic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")

    filing: Mapped["Filing"] = relationship(back_populates="risks")
    embedding_row: Mapped["RiskEmbedding"] = relationship(
        back_populates="risk", uselist=False, cascade="all, delete-orphan"
    )
    scores: Mapped[list["RiskScore"]] = relationship(back_populates="risk")


class RiskEmbedding(Base):
    __tablename__ = "risk_embeddings"

    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id"), primary_key=True)
    embedding: Mapped[Any] = mapped_column(Vector(EMBED_DIM))

    risk: Mapped["Risk"] = relationship(back_populates="embedding_row")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    title: Mapped[str] = mapped_column(String(500))
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("taxonomy.id"), nullable=True)
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBED_DIM), nullable=True)


class NewsRiskLink(Base):
    __tablename__ = "news_risk_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    news_id: Mapped[int] = mapped_column(ForeignKey("news_items.id"), index=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id"), index=True)
    similarity: Mapped[float] = mapped_column(Float)


class DriftEvent(Base):
    __tablename__ = "drift_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    from_filing_id: Mapped[int | None] = mapped_column(ForeignKey("filings.id"), nullable=True)
    to_filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"))
    risk_id: Mapped[int | None] = mapped_column(ForeignKey("risks.id"), nullable=True)
    prev_risk_id: Mapped[int | None] = mapped_column(ForeignKey("risks.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(16))  # new|removed|persisting|reworded
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)


class ToneStat(Base):
    __tablename__ = "tone_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("taxonomy.id"), nullable=True)
    neg_ratio: Mapped[float] = mapped_column(Float)
    unc_ratio: Mapped[float] = mapped_column(Float)
    mean_position: Mapped[float] = mapped_column(Float)
    risk_count: Mapped[int] = mapped_column(Integer)


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id"), index=True)
    p_mean: Mapped[float] = mapped_column(Float)
    p_lo: Mapped[float] = mapped_column(Float)
    p_hi: Mapped[float] = mapped_column(Float)
    alpha: Mapped[float] = mapped_column(Float)
    beta: Mapped[float] = mapped_column(Float)
    impact_usd: Mapped[float] = mapped_column(Float)
    impact_pct_ebitda: Mapped[float] = mapped_column(Float)
    impact_norm: Mapped[float] = mapped_column(Float)
    impact_band: Mapped[int] = mapped_column(Integer)
    expected_loss: Mapped[float] = mapped_column(Float)
    zone: Mapped[str] = mapped_column(String(16))  # tolerate|treat|transfer|terminate
    inputs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    fallbacks: Mapped[dict] = mapped_column(JSON, default=dict)
    scored_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    risk: Mapped["Risk"] = relationship(back_populates="scores")


class MonteCarloRun(Base):
    __tablename__ = "mc_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risks.id"), index=True)
    params_json: Mapped[dict] = mapped_column(JSON)
    seed: Mapped[int] = mapped_column(Integer)
    n_sims: Mapped[int] = mapped_column(Integer)
    mean: Mapped[float] = mapped_column(Float)
    median: Mapped[float] = mapped_column(Float)
    var95: Mapped[float] = mapped_column(Float)
    var99: Mapped[float] = mapped_column(Float)
    cvar95: Mapped[float] = mapped_column(Float)
    cvar99: Mapped[float] = mapped_column(Float)
    hist_bins_json: Mapped[dict] = mapped_column(JSON)
    exceed_json: Mapped[dict] = mapped_column(JSON)
    mitigation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
