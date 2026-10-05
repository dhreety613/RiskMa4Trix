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
