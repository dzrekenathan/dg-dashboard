from app.models import UserRole
from app import admin_accounts


def test_get_admin_role_matches_case_and_whitespace_insensitively(monkeypatch):
    monkeypatch.setitem(admin_accounts.ADMIN_ACCOUNTS, "dg@gslaw.edu.gh", UserRole.DG)
    assert admin_accounts.get_admin_role("  DG@gslaw.edu.gh  ") == UserRole.DG


def test_get_admin_role_returns_none_for_unknown_email():
    assert admin_accounts.get_admin_role("nobody@gslaw.edu.gh") is None
