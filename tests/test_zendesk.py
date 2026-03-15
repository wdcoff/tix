"""Tests for tix.services.zendesk.ZendeskService."""

import httpx
import pytest

from tix.errors import ZendeskAPIError
from tix.services.zendesk import ZendeskService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_SUBDOMAIN = "testcorp"
FAKE_EMAIL = "agent@example.com"
FAKE_TOKEN = "tok_abc123"

BASE_URL = f"https://{FAKE_SUBDOMAIN}.zendesk.com/api/v2"


def _make_service(transport: httpx.MockTransport) -> ZendeskService:
    """Build a ZendeskService with its HTTP client replaced by a mock."""
    svc = ZendeskService(FAKE_SUBDOMAIN, FAKE_EMAIL, FAKE_TOKEN)
    svc.client = httpx.Client(
        transport=transport,
        base_url=BASE_URL,
        auth=(f"{FAKE_EMAIL}/token", FAKE_TOKEN),
    )
    return svc


# ---------------------------------------------------------------------------
# fetch_open_tickets
# ---------------------------------------------------------------------------


def test_fetch_open_tickets_success():
    tickets = [
        {"id": 1, "subject": "Printer on fire", "status": "open"},
        {"id": 2, "subject": "Cannot login", "status": "open"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2/search.json"
        return httpx.Response(200, json={"results": tickets, "count": 2})

    svc = _make_service(httpx.MockTransport(handler))
    result = svc.fetch_open_tickets()

    assert result == tickets
    assert len(result) == 2
    assert result[0]["subject"] == "Printer on fire"


def test_fetch_open_tickets_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    svc = _make_service(httpx.MockTransport(handler))

    with pytest.raises(ZendeskAPIError, match="Zendesk API error 500"):
        svc.fetch_open_tickets()


def test_fetch_open_tickets_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    svc = _make_service(httpx.MockTransport(handler))

    with pytest.raises(ZendeskAPIError, match="Zendesk unreachable"):
        svc.fetch_open_tickets()


# ---------------------------------------------------------------------------
# subdomain validation
# ---------------------------------------------------------------------------


def test_subdomain_validation_rejects_invalid():
    for bad in ["-leading-dash", "", "has spaces", "semi;colon", "under_score"]:
        with pytest.raises(ValueError, match="Invalid Zendesk subdomain"):
            ZendeskService(bad, FAKE_EMAIL, FAKE_TOKEN)


def test_subdomain_validation_accepts_valid():
    for good in ["acme", "my-company", "test123", "A1-corp"]:
        svc = ZendeskService(good, FAKE_EMAIL, FAKE_TOKEN)
        svc.close()
