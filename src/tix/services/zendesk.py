import logging
import re

import httpx

from tix.errors import ZendeskAPIError

logger = logging.getLogger(__name__)


class ZendeskService:
    """Thin client for the Zendesk REST API (v2).

    Owns a persistent ``httpx.Client`` for connection reuse.
    Use as a context manager or call :meth:`close` explicitly.
    """

    def __init__(self, subdomain: str, email: str, token: str):
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-]*$", subdomain):
            raise ValueError(f"Invalid Zendesk subdomain: {subdomain}")

        self.client = httpx.Client(
            base_url=f"https://{subdomain}.zendesk.com/api/v2",
            auth=(f"{email}/token", token),
            timeout=30.0,
            follow_redirects=False,
        )

    # -- tickets ---------------------------------------------------------------

    def fetch_open_tickets(self) -> list[dict]:
        """Fetch all open tickets via Zendesk Search API. Returns raw ticket dicts."""
        try:
            resp = self.client.get(
                "/search.json",
                params={"query": "type:ticket status:open", "per_page": 100},
            )
            resp.raise_for_status()
            results = resp.json()["results"]
            logger.info("Fetched %d open tickets from Zendesk", len(results))
            return results
        except httpx.HTTPStatusError as e:
            logger.warning("Zendesk API error %d: %s", e.response.status_code, e.response.text[:200])
            raise ZendeskAPIError(
                f"Zendesk API error {e.response.status_code}: "
                f"{e.response.text[:200]}"
            ) from e
        except httpx.RequestError as e:
            logger.warning("Zendesk unreachable: %s", e)
            raise ZendeskAPIError(f"Zendesk unreachable: {e}") from e

    # -- custom statuses -------------------------------------------------------

    def fetch_custom_statuses(self) -> dict[int, str]:
        """Fetch custom ticket statuses. Returns ``{custom_status_id: agent_label}``."""
        try:
            resp = self.client.get("/custom_statuses.json")
            resp.raise_for_status()
            statuses = resp.json().get("custom_statuses", [])
            return {
                s["id"]: s["agent_label"]
                for s in statuses
                if s.get("active", True)
            }
        except httpx.HTTPStatusError as e:
            # Custom statuses may not be enabled -- return empty map.
            if e.response.status_code == 404:
                return {}
            raise ZendeskAPIError(
                f"Zendesk API error {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise ZendeskAPIError(f"Zendesk unreachable: {e}") from e

    # -- lifecycle -------------------------------------------------------------

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
