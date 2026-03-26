"""Tests for cross-platform identity resolution."""
import pytest
from pathlib import Path
from skillforge.core.identity_resolver import IdentityResolver


@pytest.fixture
def resolver(tmp_path):
    return IdentityResolver(data_dir=tmp_path)


class TestIdentityResolver:

    def test_no_mapping_returns_raw_id(self, resolver):
        assert resolver.resolve("telegram:12345") == "telegram:12345"

    def test_link_and_resolve(self, resolver):
        resolver.link("admin", "telegram:12345")
        resolver.link("admin", "whatsapp:+923001234567")
        assert resolver.resolve("telegram:12345") == "admin"
        assert resolver.resolve("whatsapp:+923001234567") == "admin"

    def test_unlink(self, resolver):
        resolver.link("admin", "telegram:12345")
        resolver.unlink("telegram:12345")
        assert resolver.resolve("telegram:12345") == "telegram:12345"

    def test_get_aliases(self, resolver):
        resolver.link("admin", "telegram:12345")
        resolver.link("admin", "whatsapp:+923001234567")
        resolver.link("admin", "web:admin@email.com")
        aliases = resolver.get_aliases("admin")
        assert len(aliases) == 3
        assert "telegram:12345" in aliases

    def test_get_all_users(self, resolver):
        resolver.link("admin", "telegram:111")
        resolver.link("user1", "whatsapp:+123")
        users = resolver.get_all_users()
        assert "admin" in users
        assert "user1" in users

    def test_persistence(self, tmp_path):
        r1 = IdentityResolver(data_dir=tmp_path)
        r1.link("admin", "telegram:12345")
        r2 = IdentityResolver(data_dir=tmp_path)
        assert r2.resolve("telegram:12345") == "admin"

    def test_duplicate_link_overwrites(self, resolver):
        resolver.link("user1", "telegram:12345")
        resolver.link("admin", "telegram:12345")
        assert resolver.resolve("telegram:12345") == "admin"

    def test_remove_user(self, resolver):
        resolver.link("admin", "telegram:111")
        resolver.link("admin", "whatsapp:222")
        resolver.remove_user("admin")
        assert resolver.resolve("telegram:111") == "telegram:111"
        assert resolver.get_aliases("admin") == []
