"""Abstract repository interface for loading, saving, and rolling back SiteConfigs."""

from abc import ABC, abstractmethod
from domain.site_config import SiteConfig


class ConfigRepository(ABC):
    """Abstract interface for SiteConfig storage."""

    @abstractmethod
    async def get_active_config(self, site_name: str) -> SiteConfig | None:
        """Fetch the current active production config for a site."""
        pass

    @abstractmethod
    async def save_config(self, config: SiteConfig) -> None:
        """Save a new config version and promote it to active status."""
        pass

    @abstractmethod
    async def list_versions(self, site_name: str) -> list[int]:
        """List all available version numbers for a site."""
        pass

    @abstractmethod
    async def rollback(self, site_name: str, target_version: int) -> SiteConfig | None:
        """Roll back active config to a previous version number."""
        pass
