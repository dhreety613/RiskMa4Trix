from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    cik: str
    name: str
    sector: str | None
    sic: str | None
    created_at: datetime


class FilingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    accession: str
    form_type: str
    fiscal_year: int
    filed_date: date
    url: str
    has_item1a: bool
    has_item7: bool
    has_item7a: bool


class IngestAck(BaseModel):
    ticker: str
    status: str


class MatrixPointOut(BaseModel):
    risk_id: int
    title: str
    category: str | None
    category_name: str | None
    p_mean: float
    impact_norm: float
    impact_pct_ebitda: float
    expected_loss: float
    zone: str
    is_generic: bool
    is_assumption_driven: bool


class DriftEventOut(BaseModel):
    id: int
    from_fiscal_year: int | None
    to_fiscal_year: int
    label: str
    similarity: float | None
    title: str
    category_id: int | None


class RiskCardOut(BaseModel):
    risk_id: int
    ticker: str
    title: str
    text_excerpt: str
    category: str | None
    category_name: str | None
    zone: str | None
    p_mean: float | None
    p_lo: float | None
    p_hi: float | None
    impact_usd: float | None
    impact_pct_ebitda: float | None
    expected_loss: float | None
    is_generic: bool
    generic_score: float | None
    is_assumption_driven: bool
    fallbacks: list[str]
    can_run_monte_carlo: bool
