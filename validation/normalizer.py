"""Record normalizer converting raw parsed dicts to canonical formats."""

from typing import Any
from urllib.parse import urljoin
import re


class RecordNormalizer:
    """Normalizes raw string fields (trimming whitespace, making URLs absolute, cleaning dates)."""

    def __init__(self, base_url: str, site_name: str):
        self.base_url = base_url
        self.site_name = site_name

    def normalize(self, raw_record: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}

        for key, val in raw_record.items():
            if val is None:
                normalized[key] = None
                continue

            str_val = str(val).strip()

            if key == "url":
                # Ensure fully qualified absolute URL
                if str_val.startswith("/"):
                    str_val = urljoin(self.base_url, str_val)
                elif not (str_val.startswith("http://") or str_val.startswith("https://")):
                    str_val = urljoin(self.base_url, "/" + str_val)

            elif key in ("title", "company", "location"):
                # Collapse excessive whitespaces and newlines
                str_val = re.sub(r"\s+", " ", str_val)

            normalized[key] = str_val if str_val else None

        normalized["source_site"] = self.site_name
        return normalized

    def deduplicate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate records by normalized URL."""
        seen_urls = set()
        deduped = []
        for r in records:
            url = r.get("url")
            if url:
                if url not in seen_urls:
                    seen_urls.add(url)
                    deduped.append(r)
            else:
                deduped.append(r)
        return deduped
