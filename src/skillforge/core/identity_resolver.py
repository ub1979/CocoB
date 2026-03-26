"""
Cross-platform identity resolution.

Maps platform-specific IDs (telegram:12345, whatsapp:+923001234567, web:admin@email.com)
to canonical user IDs so permissions and memory follow the person, not the platform.

Storage: data/identity_map.json
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from skillforge import PROJECT_ROOT

logger = logging.getLogger("identity_resolver")


class IdentityResolver:
    """Maps platform-specific IDs to canonical user IDs."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or (PROJECT_ROOT / "data")
        self._map_path = self._data_dir / "identity_map.json"
        self._alias_to_canonical: Dict[str, str] = {}
        self._canonical_to_aliases: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        if not self._map_path.exists():
            return
        try:
            with open(self._map_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._alias_to_canonical = data.get("alias_to_canonical", {})
            self._canonical_to_aliases = data.get("canonical_to_aliases", {})
        except Exception as e:
            logger.error("Failed to load identity_map.json: %s", e)

    def _save(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._map_path, "w", encoding="utf-8") as f:
            json.dump({
                "alias_to_canonical": self._alias_to_canonical,
                "canonical_to_aliases": self._canonical_to_aliases,
            }, f, indent=2)

    def resolve(self, platform_id: str) -> str:
        """Resolve a platform-specific ID to canonical user ID.
        Returns the raw platform_id if no mapping exists."""
        return self._alias_to_canonical.get(platform_id, platform_id)

    def link(self, canonical_id: str, platform_id: str):
        """Link a platform ID to a canonical user."""
        old_canonical = self._alias_to_canonical.get(platform_id)
        if old_canonical and old_canonical != canonical_id:
            aliases = self._canonical_to_aliases.get(old_canonical, [])
            if platform_id in aliases:
                aliases.remove(platform_id)

        self._alias_to_canonical[platform_id] = canonical_id
        aliases = self._canonical_to_aliases.setdefault(canonical_id, [])
        if platform_id not in aliases:
            aliases.append(platform_id)
        self._save()

    def unlink(self, platform_id: str):
        """Remove a platform ID mapping."""
        canonical = self._alias_to_canonical.pop(platform_id, None)
        if canonical:
            aliases = self._canonical_to_aliases.get(canonical, [])
            if platform_id in aliases:
                aliases.remove(platform_id)
        self._save()

    def get_aliases(self, canonical_id: str) -> List[str]:
        """Get all platform aliases for a canonical user."""
        return list(self._canonical_to_aliases.get(canonical_id, []))

    def get_all_users(self) -> Dict[str, List[str]]:
        """Get all canonical users and their aliases."""
        return dict(self._canonical_to_aliases)

    def remove_user(self, canonical_id: str):
        """Remove a canonical user and all their aliases."""
        aliases = self._canonical_to_aliases.pop(canonical_id, [])
        for alias in aliases:
            self._alias_to_canonical.pop(alias, None)
        self._save()
