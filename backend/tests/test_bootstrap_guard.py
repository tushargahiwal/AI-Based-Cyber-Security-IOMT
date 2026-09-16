"""Who can create the first admin.

"The users table is empty, so this account becomes an admin" is a reasonable
bootstrap on a laptop and a race anyone can win on a public URL — and a free
Hugging Face Space has no private option. Between deploying and registering,
whoever finds the address first would own the system.

Gating on "no ADMIN exists yet" rather than "no user exists" matters just as
much: the naive version lets anyone register a throwaway viewer and permanently
lock the real owner out of bootstrapping, at no cost to the attacker.

These pin both properties so a later refactor cannot quietly reopen either.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import auth_service  # noqa: E402

ADMIN_ROLE = type("Role", (), {"id": 1, "permissions": ["users.manage", "alerts.read"]})()
VIEWER_ROLE = type("Role", (), {"id": 4, "permissions": ["alerts.read"]})()


class FakeQuery:
    def __init__(self, rows, count=0):
        self._rows, self._count = rows, count

    def all(self):
        return self._rows

    def filter(self, *a, **k):
        return self

    def count(self):
        return self._count

    def first(self):
        return None


class FakeSession:
    """Enough of a Session to reach the guard and stop just after it."""

    def __init__(self, *, admin_accounts=0):
        self.admin_accounts = admin_accounts

    def query(self, model):
        if model is auth_service.Role:
            return FakeQuery([ADMIN_ROLE, VIEWER_ROLE])
        return FakeQuery([], count=self.admin_accounts)


def register(*, admin_accounts, role, token, env, configured_token, permissions=None):
    settings = auth_service.settings
    with patch.object(settings, "env", env), \
         patch.object(settings, "bootstrap_token", configured_token):
        return auth_service.register_user(
            FakeSession(admin_accounts=admin_accounts),
            username="u", email="u@example.com", password="p",
            role_name=role, full_name=None, department=None, mobile=None,
            address=None, city=None, state=None,
            requesting_permissions=permissions, bootstrap_token=token,
        )


PASSED_THE_GUARD = 400  # the fake session then fails the role lookup, which is the signal


def test_an_anonymous_admin_bootstrap_is_refused_in_production():
    """The case that matters: a public deployment before anyone has registered."""
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=0, role="admin", token=None,
                 env="production", configured_token="s3cret")
    assert exc.value.status_code == 403
    assert "X-Bootstrap-Token" in exc.value.detail


def test_a_wrong_token_is_refused():
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=0, role="admin", token="guess",
                 env="production", configured_token="s3cret")
    assert exc.value.status_code == 403


def test_the_correct_token_gets_past_the_guard():
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=0, role="admin", token="s3cret",
                 env="production", configured_token="s3cret")
    assert exc.value.status_code == PASSED_THE_GUARD


def test_a_stray_viewer_signup_cannot_lock_the_owner_out():
    """The denial-of-bootstrap this gate exists to prevent.

    Viewers may exist; what closes the bootstrap is an ADMIN existing, not a
    row existing.
    """
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=0, role="admin", token="s3cret",
                 env="production", configured_token="s3cret")
    assert exc.value.status_code == PASSED_THE_GUARD, (
        "an unprivileged account already existing must not block the real bootstrap"
    )


def test_production_without_a_configured_token_fails_closed():
    """Forgetting to set the secret must not silently leave the door open."""
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=0, role="admin", token=None,
                 env="production", configured_token="")
    assert exc.value.status_code == 403
    assert "BOOTSTRAP_TOKEN is not configured" in exc.value.detail


def test_development_with_no_token_stays_convenient():
    """Running locally should not need ceremony."""
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=0, role="admin", token=None,
                 env="development", configured_token="")
    assert exc.value.status_code == PASSED_THE_GUARD


def test_a_viewer_never_needs_the_token():
    """Self-service signup is unprivileged and must keep working."""
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=0, role="viewer", token=None,
                 env="production", configured_token="s3cret")
    assert exc.value.status_code == PASSED_THE_GUARD


def test_the_token_stops_working_once_an_admin_exists():
    """It is a bootstrap, not a permanent back door."""
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=1, role="admin", token="s3cret",
                 env="production", configured_token="s3cret")
    assert exc.value.status_code == 403
    assert "only an admin" in exc.value.detail


def test_an_authenticated_admin_still_creates_users_without_a_token():
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=1, role="admin", token=None, env="production",
                 configured_token="s3cret", permissions=["users.manage"])
    assert exc.value.status_code == PASSED_THE_GUARD


def test_a_non_admin_token_holder_cannot_escalate_an_existing_system():
    """An analyst with a leaked token must not be able to mint admins."""
    with pytest.raises(HTTPException) as exc:
        register(admin_accounts=1, role="admin", token="s3cret", env="production",
                 configured_token="s3cret", permissions=["alerts.read", "alerts.ack"])
    assert exc.value.status_code == 403


def test_the_token_is_compared_without_leaking_its_length_by_timing():
    import inspect

    source = inspect.getsource(auth_service._authorise_privileged_registration)
    assert "compare_digest" in source, (
        "a plain == on a secret can be narrowed down by timing the comparison"
    )
