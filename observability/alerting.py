"""Alerting interfaces and implementations for human escalation."""

from abc import ABC, abstractmethod
import asyncio
import httpx
from observability.logging_config import get_logger

logger = get_logger(__name__)


class AlertService(ABC):
    """Abstract interface for notifying humans of critical scraper events."""

    @abstractmethod
    async def send_alert(self, site_name: str, message: str, context: dict | None = None) -> bool:
        pass


class LogAlertService(AlertService):
    """Fallback alert service logging human escalations to structured logs."""

    async def send_alert(self, site_name: str, message: str, context: dict | None = None) -> bool:
        logger.error(
            "HUMAN_ESCALATION_ALERT",
            site_name=site_name,
            alert_message=message,
            context=context or {},
        )
        return True


class WebhookAlertService(AlertService):
    """Dispatches webhook alerts (Slack, Discord, generic HTTP POST)."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_alert(self, site_name: str, message: str, context: dict | None = None) -> bool:
        payload = {
            "text": f"🚨 [JobScraper Alert] {site_name}: {message}",
            "site_name": site_name,
            "message": message,
            "context": context or {},
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.webhook_url, json=payload)
                return res.is_success
        except Exception as e:
            logger.error("Failed to deliver webhook alert", error=str(e), url=self.webhook_url)
            return False


class CompositeAlertService(AlertService):
    """Sends alert through multiple channels (e.g. log + webhook)."""

    def __init__(self, services: list[AlertService]):
        self.services = services

    async def send_alert(self, site_name: str, message: str, context: dict | None = None) -> bool:
        results = await asyncio.gather(
            *[s.send_alert(site_name, message, context) for s in self.services],
            return_exceptions=True,
        )
        return any(r is True for r in results)
