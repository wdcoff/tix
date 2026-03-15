"""Tests for tix.services.staleness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tix.models import TicketData
from tix.services.staleness import check_staleness, update_staleness

RULES = [
    {"local": "Investigating", "ok_zendesk": ["open", "new"]},
    {"local": "Waiting", "ok_zendesk": ["pending"]},
    {"local": "Done", "ok_zendesk": ["solved", "closed"]},
]


def _make_card(
    local_column: str = "Investigating",
    zendesk_status: str = "open",
    stale_since: datetime | None = None,
) -> TicketData:
    return TicketData(
        ticket_id=1,
        subject="Test ticket",
        zendesk_status=zendesk_status,
        local_column=local_column,
        stale_since=stale_since,
    )


class TestCheckStaleness:
    """Tests for check_staleness()."""

    def test_no_matching_rule_not_stale(self) -> None:
        card = _make_card(local_column="NoSuchColumn", zendesk_status="open")
        is_stale, days = check_staleness(card, RULES)
        assert is_stale is False
        assert days == 0

    def test_matching_rule_ok_status_not_stale(self) -> None:
        card = _make_card(local_column="Investigating", zendesk_status="open")
        is_stale, days = check_staleness(card, RULES)
        assert is_stale is False
        assert days == 0

    def test_mismatch_no_stale_since_returns_false(self) -> None:
        card = _make_card(
            local_column="Investigating",
            zendesk_status="solved",
            stale_since=None,
        )
        is_stale, days = check_staleness(card, RULES)
        assert is_stale is False
        assert days == 0

    def test_mismatch_beyond_threshold_is_stale(self) -> None:
        card = _make_card(
            local_column="Investigating",
            zendesk_status="solved",
            stale_since=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        is_stale, days = check_staleness(card, RULES, warn_after_hours=24)
        assert is_stale is True
        assert days >= 1

    def test_mismatch_below_threshold_not_stale(self) -> None:
        card = _make_card(
            local_column="Investigating",
            zendesk_status="solved",
            stale_since=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        is_stale, days = check_staleness(card, RULES, warn_after_hours=24)
        assert is_stale is False
        assert days == 0

    def test_waiting_column_with_wrong_status(self) -> None:
        card = _make_card(
            local_column="Waiting",
            zendesk_status="open",
            stale_since=datetime.now(timezone.utc) - timedelta(hours=50),
        )
        is_stale, days = check_staleness(card, RULES, warn_after_hours=24)
        assert is_stale is True


class TestUpdateStaleness:
    """Tests for update_staleness()."""

    def test_sets_stale_since_on_mismatch(self) -> None:
        card = _make_card(
            local_column="Investigating",
            zendesk_status="solved",
            stale_since=None,
        )
        update_staleness(card, RULES)
        assert card.stale_since is not None
        # Should be very recent
        assert (datetime.now(timezone.utc) - card.stale_since).total_seconds() < 5

    def test_clears_stale_since_when_status_matches(self) -> None:
        card = _make_card(
            local_column="Investigating",
            zendesk_status="open",
            stale_since=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        update_staleness(card, RULES)
        assert card.stale_since is None

    def test_clears_stale_since_when_no_matching_rule(self) -> None:
        card = _make_card(
            local_column="NoSuchColumn",
            zendesk_status="open",
            stale_since=datetime.now(timezone.utc),
        )
        update_staleness(card, RULES)
        assert card.stale_since is None

    def test_preserves_existing_stale_since_on_mismatch(self) -> None:
        original_stale = datetime.now(timezone.utc) - timedelta(hours=10)
        card = _make_card(
            local_column="Done",
            zendesk_status="open",
            stale_since=original_stale,
        )
        update_staleness(card, RULES)
        # Should not overwrite existing stale_since
        assert card.stale_since == original_stale
