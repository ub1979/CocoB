"""
Permission request queue.

Users who are denied a permission can submit a request.
Admins can approve or deny requests from the admin panel or chat commands.
Storage: data/permission_requests.json
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from skillforge import PROJECT_ROOT

logger = logging.getLogger("permission_requests")


class PermissionRequestManager:
    """Manages permission requests from users to admins."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or (PROJECT_ROOT / "data")
        self._requests_path = self._data_dir / "permission_requests.json"
        self._requests: List[Dict] = []
        self._load()

    def _load(self):
        if not self._requests_path.exists():
            return
        try:
            with open(self._requests_path, "r", encoding="utf-8") as f:
                self._requests = json.load(f)
        except Exception as e:
            logger.error("Failed to load permission_requests.json: %s", e)

    def _save(self):
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._requests_path, "w", encoding="utf-8") as f:
            json.dump(self._requests, f, indent=2)

    def submit(self, user_id: str, permission: str, reason: str = "") -> Optional[str]:
        """Submit a permission request. Returns request ID, or None if duplicate pending."""
        for req in self._requests:
            if (req["user_id"] == user_id
                    and req["permission"] == permission
                    and req["status"] == "pending"):
                return None

        req_id = str(uuid.uuid4())[:8]
        self._requests.append({
            "id": req_id,
            "user_id": user_id,
            "permission": permission,
            "reason": reason,
            "status": "pending",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "approved_by": None,
            "decided_at": None,
            "deny_reason": None,
        })
        self._save()
        return req_id

    def approve(self, req_id: str, admin_id: str) -> bool:
        """Approve a pending request."""
        for req in self._requests:
            if req["id"] == req_id and req["status"] == "pending":
                req["status"] = "approved"
                req["approved_by"] = admin_id
                req["decided_at"] = datetime.now(tz=timezone.utc).isoformat()
                self._save()
                return True
        return False

    def deny(self, req_id: str, admin_id: str, reason: str = "") -> bool:
        """Deny a pending request."""
        for req in self._requests:
            if req["id"] == req_id and req["status"] == "pending":
                req["status"] = "denied"
                req["approved_by"] = admin_id
                req["decided_at"] = datetime.now(tz=timezone.utc).isoformat()
                req["deny_reason"] = reason
                self._save()
                return True
        return False

    def get_pending(self) -> List[Dict]:
        """Get all pending requests."""
        return [r for r in self._requests if r["status"] == "pending"]

    def get_user_requests(self, user_id: str) -> List[Dict]:
        """Get all requests by a specific user."""
        return [r for r in self._requests if r["user_id"] == user_id]

    def get_all(self) -> List[Dict]:
        """Get all requests."""
        return list(self._requests)
