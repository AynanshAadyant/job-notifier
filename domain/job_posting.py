"""Normalized JobPosting output contract.

All scrapers regardless of source site must emit records conforming to this model.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field, HttpUrl, field_validator


class JobPosting(BaseModel):
    """Canonical representation of a single scraped job listing."""

    title: str = Field(
        description="Job title/role name (Required)"
    )
    company: str = Field(
        description="Company or employer offering the job (Required)"
    )
    url: str = Field(
        description="Direct link to job application or listing details (Required)"
    )
    location: str | None = Field(
        default=None,
        description="Work location, e.g. Remote, City, Country"
    )
    salary: str | None = Field(
        default=None,
        description="Salary range or compensation details if disclosed"
    )
    date_posted: str | None = Field(
        default=None,
        description="Posting date or relative age string (e.g. '2 days ago', '2026-03-01')"
    )
    description: str | None = Field(
        default=None,
        description="Job description, snippet, or tags"
    )
    source_site: str = Field(
        description="Site ID/name that emitted this listing"
    )
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when record was scraped"
    )

    @field_validator("title", "company", "url")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty or only whitespace")
        return clean
