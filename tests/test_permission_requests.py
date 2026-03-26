"""Tests for permission request queue."""
import pytest
from pathlib import Path
from skillforge.core.permission_requests import PermissionRequestManager


@pytest.fixture
def mgr(tmp_path):
    return PermissionRequestManager(data_dir=tmp_path)


class TestPermissionRequests:

    def test_submit_request(self, mgr):
        req_id = mgr.submit("user1", "skills_create", "I need to create skills for my team")
        assert req_id is not None
        pending = mgr.get_pending()
        assert len(pending) == 1
        assert pending[0]["user_id"] == "user1"
        assert pending[0]["permission"] == "skills_create"
        assert pending[0]["status"] == "pending"

    def test_approve_request(self, mgr):
        req_id = mgr.submit("user1", "web_search")
        result = mgr.approve(req_id, "admin1")
        assert result is True
        pending = mgr.get_pending()
        assert len(pending) == 0

    def test_deny_request(self, mgr):
        req_id = mgr.submit("user1", "web_search")
        result = mgr.deny(req_id, "admin1", reason="Not needed")
        assert result is True
        pending = mgr.get_pending()
        assert len(pending) == 0

    def test_get_user_requests(self, mgr):
        mgr.submit("user1", "web_search")
        mgr.submit("user1", "schedule")
        mgr.submit("user2", "files")
        reqs = mgr.get_user_requests("user1")
        assert len(reqs) == 2

    def test_duplicate_pending_rejected(self, mgr):
        mgr.submit("user1", "web_search")
        req_id2 = mgr.submit("user1", "web_search")
        assert req_id2 is None
        assert len(mgr.get_pending()) == 1

    def test_persistence(self, tmp_path):
        m1 = PermissionRequestManager(data_dir=tmp_path)
        m1.submit("user1", "web_search")
        m2 = PermissionRequestManager(data_dir=tmp_path)
        assert len(m2.get_pending()) == 1

    def test_approve_nonexistent(self, mgr):
        assert mgr.approve("fake-id", "admin") is False

    def test_request_has_timestamp(self, mgr):
        mgr.submit("user1", "schedule")
        pending = mgr.get_pending()
        assert "timestamp" in pending[0]

    def test_approved_request_includes_approver(self, mgr):
        req_id = mgr.submit("user1", "schedule")
        mgr.approve(req_id, "admin1")
        history = mgr.get_user_requests("user1")
        assert history[0]["approved_by"] == "admin1"
