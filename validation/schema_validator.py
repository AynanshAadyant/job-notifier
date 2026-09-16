"""Schema validator verifying records against JobPosting contract."""

from typing import Any
from pydantic import ValidationError
from domain.job_posting import JobPosting


class ValidationResult:
    def __init__(self):
        self.valid_postings: list[JobPosting] = []
        self.rejected_records: list[tuple[dict[str, Any], str]] = []

    @property
    def total_count(self) -> int:
        return len(self.valid_postings) + len(self.rejected_records)

    @property
    def rejection_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return len(self.rejected_records) / self.total_count


class SchemaValidator:
    """Validates and parses raw dictionary records into strict JobPosting domain objects."""

    def validate_all(self, records: list[dict[str, Any]]) -> ValidationResult:
        result = ValidationResult()
        for record in records:
            try:
                # Enforce title, company, url presence
                if not record.get("title") or not record.get("company") or not record.get("url"):
                    missing = [
                        k for k in ("title", "company", "url") if not record.get(k)
                    ]
                    result.rejected_records.append(
                        (record, f"Missing required fields: {', '.join(missing)}")
                    )
                    continue

                posting = JobPosting(**record)
                result.valid_postings.append(posting)
            except ValidationError as e:
                result.rejected_records.append((record, str(e)))
            except Exception as e:
                result.rejected_records.append((record, f"Unexpected error: {e}"))

        return result
