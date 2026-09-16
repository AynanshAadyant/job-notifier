"""Config generator interface."""

from abc import ABC, abstractmethod
from domain.site_config import SiteConfig


class ConfigGenerator(ABC):
    """Abstract interface for generating updated SiteConfig data."""

    @abstractmethod
    async def generate(
        self,
        html_sample: str,
        failure_context: str,
        current_config: SiteConfig,
    ) -> SiteConfig:
        """Generate a healed candidate SiteConfig.

        Must emit structured data only — never executable code.
        """
        pass
