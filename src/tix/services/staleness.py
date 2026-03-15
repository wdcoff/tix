"""Staleness engine.

Updates stale_since on tickets whose local board column no longer
matches the expected Zendesk status, based on configurable rules.
"""
from __future__ import annotations

from datetime import datetime, timezone

from tix.models import TicketData


def update_staleness(
    card: TicketData,
    rules: list[dict],
) -> None:
    """Update ``stale_since`` on a card based on current status mismatch.

    Call this after sync or card move.  Mutates *card* in place.
    """
    matching_rule = None
    for rule in rules:
        if rule.get("local") == card.local_column:
            matching_rule = rule
            break

    if matching_rule is None:
        card.stale_since = None
        return

    ok_statuses = matching_rule.get("ok_zendesk", [])
    if card.zendesk_status in ok_statuses:
        card.stale_since = None
    elif card.stale_since is None:
        card.stale_since = datetime.now(timezone.utc)
