"""Staleness engine.

Detects tickets whose local board column no longer matches the
expected Zendesk status, based on configurable rules.
"""
from __future__ import annotations

from datetime import datetime, timezone

from tix.models import TicketData


def check_staleness(
    card: TicketData,
    rules: list[dict],  # [{"local": "Needs Notify", "ok_zendesk": ["solved", "pending"]}, ...]
    warn_after_hours: int = 24,
) -> tuple[bool, int]:
    """Check if a card is stale based on configured rules.

    Returns ``(is_stale, stale_days)``.

    A card is stale when:

    1. Its ``local_column`` matches a rule's ``"local"`` field.
    2. Its ``zendesk_status`` is **not** in the rule's ``"ok_zendesk"`` list.
    3. The mismatch has persisted for longer than *warn_after_hours*.
    """
    # Find matching rule for this card's column
    matching_rule = None
    for rule in rules:
        if rule.get("local") == card.local_column:
            matching_rule = rule
            break

    if matching_rule is None:
        # No rule for this column -- not stale
        return (False, 0)

    ok_statuses = matching_rule.get("ok_zendesk", [])
    if card.zendesk_status in ok_statuses:
        # Zendesk status matches expected -- not stale
        return (False, 0)

    # Status mismatch detected
    if card.stale_since is None:
        # Just detected -- will be marked stale_since by caller
        return (False, 0)

    now = datetime.now(timezone.utc)
    stale_duration = now - card.stale_since
    stale_hours = stale_duration.total_seconds() / 3600
    stale_days = max(0, int(stale_duration.total_seconds() / 86400))

    if stale_hours >= warn_after_hours:
        return (True, stale_days)

    return (False, 0)


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
