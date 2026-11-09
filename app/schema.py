from datetime import date

from pydantic import BaseModel, Field


class ContractFields(BaseModel):
    """The fields we ask the model for. Anything not stated in the contract must be null."""

    title: str | None = None
    parties: list[str] = Field(default_factory=list)
    effective_date: date | None = None
    governing_law: str | None = Field(None, description="Jurisdiction, e.g. 'Delaware'")
    term: str | None = Field(None, description="Duration as written, e.g. '3 years'")
    termination_notice_days: int | None = Field(None, ge=0)
    payment_terms: str | None = None
