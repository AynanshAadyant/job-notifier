"""File-based JSON configuration repository with version history and rollback."""

from pathlib import Path
import json
import asyncio
from domain.site_config import SiteConfig
from persistence.config_repository_interface import ConfigRepository


class FileConfigRepository(ConfigRepository):
    """Stores SiteConfigs as versioned JSON files in a dedicated directory.

    Files are laid out as:
      configs/{site_name}.json        <- active production config
      configs/{site_name}.v{N}.json   <- archived versions for rollback/diff
    """

    def __init__(self, configs_dir: Path | str):
        self.configs_dir = Path(configs_dir)
        self.configs_dir.mkdir(parents=True, exist_ok=True)

    def _active_path(self, site_name: str) -> Path:
        return self.configs_dir / f"{site_name}.json"

    def _version_path(self, site_name: str, version: int) -> Path:
        return self.configs_dir / f"{site_name}.v{version}.json"

    async def get_active_config(self, site_name: str) -> SiteConfig | None:
        def _read():
            path = self._active_path(site_name)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SiteConfig(**data)

        return await asyncio.to_thread(_read)

    async def save_config(self, config: SiteConfig) -> None:
        def _write():
            data = config.model_dump(mode="json")
            # 1. Save versioned copy
            version_path = self._version_path(config.site_name, config.version)
            with open(version_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            # 2. Atomically update active copy
            active_path = self._active_path(config.site_name)
            temp_path = self.configs_dir / f"{config.site_name}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            temp_path.replace(active_path)

        await asyncio.to_thread(_write)

    async def list_versions(self, site_name: str) -> list[int]:
        def _list():
            versions = []
            prefix = f"{site_name}.v"
            for p in self.configs_dir.glob(f"{prefix}*.json"):
                name = p.stem
                try:
                    v_str = name.split(".v")[-1]
                    versions.append(int(v_str))
                except ValueError:
                    pass
            return sorted(versions)

        return await asyncio.to_thread(_list)

    async def rollback(self, site_name: str, target_version: int) -> SiteConfig | None:
        def _rollback():
            vpath = self._version_path(site_name, target_version)
            if not vpath.exists():
                return None
            with open(vpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = SiteConfig(**data)

            active_path = self._active_path(site_name)
            with open(active_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            return config

        return await asyncio.to_thread(_rollback)
