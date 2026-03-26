"""Tests for admin login and credential management."""
import pytest
from pathlib import Path
from skillforge.flet.storage import SecureStorage


@pytest.fixture
def storage(tmp_path):
    return SecureStorage(storage_dir=tmp_path)


class TestAdminCredentials:

    def test_no_admin_by_default(self, storage):
        assert storage.has_admin() is False

    def test_set_and_verify_admin(self, storage):
        storage.set_admin_credentials("admin", "securepass123")
        assert storage.has_admin() is True
        assert storage.verify_admin("admin", "securepass123") is True

    def test_wrong_password_rejected(self, storage):
        storage.set_admin_credentials("admin", "securepass123")
        assert storage.verify_admin("admin", "wrongpass") is False

    def test_wrong_username_rejected(self, storage):
        storage.set_admin_credentials("admin", "securepass123")
        assert storage.verify_admin("other", "securepass123") is False

    def test_get_admin_username(self, storage):
        storage.set_admin_credentials("myuser", "pass123")
        assert storage.get_admin_username() == "myuser"

    def test_admin_persists(self, tmp_path):
        s1 = SecureStorage(storage_dir=tmp_path)
        s1.set_admin_credentials("admin", "pass123")
        s2 = SecureStorage(storage_dir=tmp_path)
        assert s2.has_admin() is True
        assert s2.verify_admin("admin", "pass123") is True
