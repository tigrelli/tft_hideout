import pytest

from services.kpi_auth import issue_token, verify_password, verify_token


@pytest.fixture(autouse=True)
def _kpi_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KPI_DASHBOARD_PASSWORD", "correct-horse-battery-staple")


def test_verify_password_accepts_correct_password() -> None:
    assert verify_password("correct-horse-battery-staple") is True


def test_verify_password_rejects_wrong_password() -> None:
    assert verify_password("wrong-password") is False


def test_issued_token_is_valid_immediately() -> None:
    token = issue_token(now=1_000_000)
    assert verify_token(token, now=1_000_000) is True


def test_token_is_invalid_after_ttl_expires() -> None:
    token = issue_token(now=1_000_000)
    just_after_expiry = 1_000_000 + 60 * 60 * 12 + 1
    assert verify_token(token, now=just_after_expiry) is False


def test_token_with_tampered_payload_is_rejected() -> None:
    token = issue_token(now=1_000_000)
    payload, signature = token.split(".", 1)
    tampered = f"{int(payload) + 999999}.{signature}"
    assert verify_token(tampered, now=1_000_000) is False


def test_malformed_token_is_rejected() -> None:
    assert verify_token("not-a-valid-token") is False
