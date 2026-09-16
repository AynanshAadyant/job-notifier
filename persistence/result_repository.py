"""Scrape result persistence repository."""

from pathlib import Path
import json
import asyncio
from datetime import datetime
from domain.results import ScrapeResult


class ResultRepository:
    """Stores scrape results and job postings for auditing and historical anomaly baseline."""

    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def save_result(self, result: ScrapeResult) -> Path:
        def _save() -> Path:
            site_dir = self.output_dir / result.site_name
            site_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_path = site_dir / f"scrape_{timestamp}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(mode="json"), f, indent=2, default=str)
            return file_path

        return await asyncio.to_thread(_save)

    async def get_historical_avg(self, site_name: str, max_lookback: int = 5) -> float | None:
        def _calc() -> float | None:
            site_dir = self.output_dir / site_name
            if not site_dir.exists():
                return None
            files = sorted(site_dir.glob("scrape_*.json"), reverse=True)[:max_lookback]
            if not files:
                return None
            counts = []
            for fpath in files:
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        counts.append(len(data.get("postings", [])))
                except Exception:
                    pass
            return sum(counts) / len(counts) if counts else None

        return await asyncio.to_thread(_calc)
