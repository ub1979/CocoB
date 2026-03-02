# =============================================================================
'''
    File Name : clawhub.py

    Description : ClawHub Manager — search, install, and manage skills from
                  OpenClaw.ai's ClawHub community registry. Skills are SKILL.md
                  files (YAML frontmatter + markdown), same format as coco B.

    Created on 2026-02-24

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : coco B - Persistent Memory AI Chatbot

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================

import io
import json
import logging
import time
import urllib.request
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from coco_b.core.skills.manager import SkillsManager

logger = logging.getLogger("clawhub")

# =============================================================================
# Default registry URL
# =============================================================================

DEFAULT_REGISTRY_URL = "https://clawhub.ai/api"
DEFAULT_CACHE_TTL = 300  # 5 minutes


# =============================================================================
'''
    ClawHubManager : Search, install, and manage skills from ClawHub registry
'''
# =============================================================================

class ClawHubManager:
    """Search, install, and manage skills from OpenClaw.ai's ClawHub registry."""

    def __init__(
        self,
        skills_manager: Optional["SkillsManager"] = None,
        registry_url: str = DEFAULT_REGISTRY_URL,
        install_dir: Optional[Path] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL,
    ):
        """Initialize ClawHub manager.

        Args:
            skills_manager: SkillsManager instance for reloading after install
            registry_url: Base URL for the ClawHub API
            install_dir: Directory for installed ClawHub skills
            cache_ttl_seconds: How long to cache search results (seconds)
        """
        self._skills_manager = skills_manager
        self._registry_url = registry_url.rstrip("/")
        self._cache_ttl = cache_ttl_seconds

        if install_dir is None:
            from coco_b import PROJECT_ROOT
            self._install_dir = PROJECT_ROOT / "skills" / "clawhub"
        else:
            self._install_dir = Path(install_dir)

        # Tracking file for installed skills
        from coco_b import PROJECT_ROOT
        self._tracking_file = PROJECT_ROOT / "data" / "clawhub_installed.json"

        # Simple in-memory cache: {cache_key: (timestamp, data)}
        self._cache: Dict[str, tuple] = {}

    # =========================================================================
    # HTTP helpers
    # =========================================================================

    def _api_get(self, path: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """HTTP GET to registry API.

        Args:
            path: API path (e.g., "/skills/search")
            params: Query parameters

        Returns:
            Parsed JSON response, or None on error
        """
        url = f"{self._registry_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"ClawHub API error ({url}): {e}")
            return None

    def _get_cached(self, key: str) -> Optional[Any]:
        """Return cached value if still fresh."""
        entry = self._cache.get(key)
        if entry and (time.time() - entry[0]) < self._cache_ttl:
            return entry[1]
        return None

    def _set_cache(self, key: str, value: Any):
        """Store value in cache."""
        self._cache[key] = (time.time(), value)

    # =========================================================================
    # Tracking file helpers
    # =========================================================================

    def _load_tracking(self) -> Dict[str, Any]:
        """Load installed skills tracking file."""
        if not self._tracking_file.exists():
            return {}
        try:
            return json.loads(self._tracking_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_tracking(self, data: Dict[str, Any]) -> bool:
        """Save installed skills tracking file."""
        try:
            self._tracking_file.parent.mkdir(parents=True, exist_ok=True)
            self._tracking_file.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
            return True
        except IOError as e:
            logger.error(f"Failed to save tracking: {e}")
            return False

    # =========================================================================
    # Search
    # =========================================================================

    def search(self, query: str, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """Search ClawHub registry for skills.

        Args:
            query: Search query
            limit: Max results to return

        Returns:
            List of skill result dicts, or None on error
        """
        cache_key = f"search:{query}:{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._api_get("/search", {"q": query, "limit": str(limit)})
        if data is None:
            return None

        results = data.get("results", data.get("skills", []))
        # Normalize field names: API returns displayName/summary, code expects name/description
        for r in results:
            if "displayName" in r and "name" not in r:
                r["name"] = r["displayName"]
            if "summary" in r and "description" not in r:
                r["description"] = r["summary"]
        self._set_cache(cache_key, results)
        return results

    # =========================================================================
    # Skill info
    # =========================================================================

    def get_skill_info(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get detailed info for a skill by slug.

        Uses search endpoint with exact slug match since the individual
        skill detail endpoint is not available on the current API.

        Args:
            slug: Skill slug (e.g., "weather-forecast")

        Returns:
            Skill info dict, or None on error
        """
        cache_key = f"info:{slug}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        # Search for the exact slug
        data = self._api_get("/search", {"q": slug, "limit": "5"})
        if data:
            results = data.get("results", [])
            # Find exact slug match
            for r in results:
                if r.get("slug") == slug:
                    # Add download_url for install flow
                    r["download_url"] = f"{self._registry_url}/download?slug={slug}"
                    self._set_cache(cache_key, r)
                    return r
            # Fallback to first result if slug is close
            if results:
                r = results[0]
                r["download_url"] = f"{self._registry_url}/download?slug={r['slug']}"
                self._set_cache(cache_key, r)
                return r
        return None

    # =========================================================================
    # Install
    # =========================================================================

    def install_skill(self, slug: str, version: str = "latest") -> tuple[bool, str]:
        """Download and install a skill from ClawHub.

        Args:
            slug: Skill slug
            version: Version to install (default "latest")

        Returns:
            (success, message) tuple
        """
        # Check if already installed
        tracking = self._load_tracking()
        if slug in tracking:
            return False, f"Skill '{slug}' is already installed. Use `/clawhub uninstall {slug}` first."

        # Get skill info
        info = self.get_skill_info(slug)
        if info is None:
            return False, f"Could not find skill '{slug}' on ClawHub."

        # Download skill content
        download_url = info.get("download_url") or info.get("content_url")
        skill_content = info.get("content")

        if download_url and not skill_content:
            try:
                req = urllib.request.Request(download_url)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read()

                # Check if it's a ZIP
                if download_url.endswith(".zip") or raw[:4] == b'PK\x03\x04':
                    skill_content = self._extract_skill_from_zip(raw)
                else:
                    skill_content = raw.decode("utf-8")
            except Exception as e:
                return False, f"Download failed: {e}"

        if not skill_content:
            return False, f"No skill content available for '{slug}'."

        # Parse with OpenClaw format adapter
        from coco_b.core.skills.loader import parse_openclaw_skill_content

        skill_dir = self._install_dir / slug
        skill = parse_openclaw_skill_content(
            skill_content, str(skill_dir / "SKILL.md"), str(skill_dir)
        )
        if skill is None:
            return False, f"Failed to parse skill content for '{slug}'."

        # Check for name conflict with bundled skills
        install_name = slug
        if self._skills_manager:
            existing = self._skills_manager.get_skill(skill.name)
            if existing and existing.source != "clawhub":
                install_name = f"ch-{slug}"
                skill.name = install_name
                logger.warning(f"Name conflict: '{slug}' renamed to '{install_name}' to avoid shadowing bundled skill")

        # Write skill file
        skill_dir = self._install_dir / install_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(skill_content, encoding="utf-8")

        # Set clawhub_slug for update tracking
        skill.clawhub_slug = slug
        skill.source = "clawhub"
        skill.file_path = str(skill_file)
        skill.version = info.get("version", version)
        skill.author = info.get("author", "")

        # Update tracking
        tracking[slug] = {
            "install_name": install_name,
            "version": skill.version,
            "author": skill.author,
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "file_path": str(skill_file),
        }
        self._save_tracking(tracking)

        # Reload skills if manager available
        if self._skills_manager:
            self._skills_manager.load_all_skills()

        conflict_note = ""
        if install_name != slug:
            conflict_note = f"\n**Note:** Renamed to `{install_name}` to avoid conflict with bundled skill."

        return True, f"Installed **{skill.get_display_name()}** (v{skill.version}) by {skill.author}.{conflict_note}"

    def _extract_skill_from_zip(self, raw: bytes) -> Optional[str]:
        """Extract SKILL.md content from a ZIP archive."""
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for name in zf.namelist():
                    if name.endswith("SKILL.md"):
                        return zf.read(name).decode("utf-8")
        except Exception as e:
            logger.error(f"ZIP extraction failed: {e}")
        return None

    # =========================================================================
    # Uninstall
    # =========================================================================

    def uninstall_skill(self, slug: str) -> tuple[bool, str]:
        """Remove an installed ClawHub skill.

        Args:
            slug: Skill slug

        Returns:
            (success, message) tuple
        """
        tracking = self._load_tracking()
        if slug not in tracking:
            return False, f"Skill '{slug}' is not installed from ClawHub."

        entry = tracking[slug]
        install_name = entry.get("install_name", slug)
        skill_dir = self._install_dir / install_name

        # Remove files
        if skill_dir.exists():
            import shutil
            shutil.rmtree(skill_dir)

        # Remove from tracking
        del tracking[slug]
        self._save_tracking(tracking)

        # Reload skills
        if self._skills_manager:
            self._skills_manager.load_all_skills()

        return True, f"Uninstalled '{slug}'."

    # =========================================================================
    # List installed
    # =========================================================================

    def list_installed(self) -> List[Dict[str, Any]]:
        """List installed ClawHub skills with version info.

        Returns:
            List of installed skill dicts
        """
        tracking = self._load_tracking()
        result = []
        for slug, entry in tracking.items():
            result.append({
                "slug": slug,
                "install_name": entry.get("install_name", slug),
                "version": entry.get("version", "unknown"),
                "author": entry.get("author", ""),
                "installed_at": entry.get("installed_at", ""),
            })
        return result

    # =========================================================================
    # Check updates
    # =========================================================================

    def check_updates(self) -> List[Dict[str, Any]]:
        """Check installed skills for available updates.

        Returns:
            List of skills that have newer versions available
        """
        tracking = self._load_tracking()
        updates = []

        for slug, entry in tracking.items():
            info = self.get_skill_info(slug)
            if info is None:
                continue
            latest_version = info.get("version", "")
            installed_version = entry.get("version", "")
            if latest_version and installed_version and latest_version != installed_version:
                updates.append({
                    "slug": slug,
                    "installed_version": installed_version,
                    "latest_version": latest_version,
                })

        return updates

    # =========================================================================
    # Requirements check
    # =========================================================================

    def check_requirements(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Check if skill requirements (bins, env) are met.

        Args:
            info: Skill info dict with optional 'requires' field

        Returns:
            Dict with 'bins_ok', 'env_ok', 'missing_bins', 'missing_env'
        """
        import shutil
        import os

        requires = info.get("requires", {})
        if not isinstance(requires, dict):
            return {"bins_ok": True, "env_ok": True, "missing_bins": [], "missing_env": []}

        required_bins = requires.get("bins", [])
        required_env = requires.get("env", [])

        missing_bins = [b for b in required_bins if shutil.which(b) is None]
        missing_env = [e for e in required_env if not os.environ.get(e)]

        return {
            "bins_ok": len(missing_bins) == 0,
            "env_ok": len(missing_env) == 0,
            "missing_bins": missing_bins,
            "missing_env": missing_env,
        }

    # =========================================================================
    # Chat-friendly formatters
    # =========================================================================

    def format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format search results for chat display."""
        if not results:
            return "No skills found."

        lines = [f"**ClawHub Results** ({len(results)} skills):\n"]
        for r in results:
            emoji = r.get("emoji", "📦")
            name = r.get("name", r.get("slug", "unknown"))
            desc = r.get("description", "")
            author = r.get("author", "")
            downloads = r.get("downloads", 0)
            slug = r.get("slug", name)

            lines.append(f"- {emoji} **{name}** — {desc}")
            if author or downloads:
                parts = []
                if author:
                    parts.append(f"by {author}")
                if downloads:
                    parts.append(f"{downloads:,} installs")
                lines.append(f"  _({', '.join(parts)})_")
            lines.append(f"  Install: `/clawhub install {slug}`")

        return "\n".join(lines)

    def format_skill_info(self, info: Dict[str, Any]) -> str:
        """Format detailed skill info for chat display."""
        if not info:
            return "Skill not found."

        emoji = info.get("emoji", "📦")
        name = info.get("name", "unknown")
        desc = info.get("description", "")
        author = info.get("author", "")
        version = info.get("version", "")
        downloads = info.get("downloads", 0)
        slug = info.get("slug", name)

        lines = [f"**{emoji} {name}**"]
        if desc:
            lines.append(desc)
        lines.append("")
        if author:
            lines.append(f"**Author:** {author}")
        if version:
            lines.append(f"**Version:** {version}")
        if downloads:
            lines.append(f"**Downloads:** {downloads:,}")

        # Requirements
        req_check = self.check_requirements(info)
        if req_check["missing_bins"]:
            lines.append(f"**Missing binaries:** {', '.join(req_check['missing_bins'])}")
        if req_check["missing_env"]:
            lines.append(f"**Missing env vars:** {', '.join(req_check['missing_env'])}")

        lines.append(f"\nInstall: `/clawhub install {slug}`")
        return "\n".join(lines)

    def format_installed_list(self) -> str:
        """Format installed skills list for chat display."""
        installed = self.list_installed()
        if not installed:
            return "No ClawHub skills installed. Use `/clawhub search <query>` to find skills."

        lines = ["**Installed ClawHub Skills:**\n"]
        for s in installed:
            slug = s["slug"]
            version = s.get("version", "?")
            author = s.get("author", "")
            author_str = f" by {author}" if author else ""
            lines.append(f"- **{slug}** v{version}{author_str}")
            lines.append(f"  Uninstall: `/clawhub uninstall {slug}`")

        return "\n".join(lines)

    def format_updates(self, updates: List[Dict[str, Any]]) -> str:
        """Format update check results for chat display."""
        if not updates:
            return "All ClawHub skills are up to date."

        lines = ["**Updates Available:**\n"]
        for u in updates:
            lines.append(f"- **{u['slug']}**: v{u['installed_version']} → v{u['latest_version']}")
            lines.append(f"  Update: `/clawhub uninstall {u['slug']}` then `/clawhub install {u['slug']}`")

        return "\n".join(lines)


# =============================================================================
'''
    End of File : clawhub.py

    Project : coco B - Persistent Memory AI Chatbot

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    License : Open Source - Safe Open Community Project
'''
# =============================================================================
