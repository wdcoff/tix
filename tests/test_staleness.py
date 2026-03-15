"""Tests for tix.services.staleness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tix.config import DEFAULT_STALENESS_RULES
from tix.models import TicketData
from tix.services.staleness import update_staleness

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


class TestDefaultStalenessRulesIntegration:
    """Verify DEFAULT_STALENESS_RULES from config.py work with the staleness engine."""

    def test_default_rules_have_correct_schema(self) -> None:
        for rule in DEFAULT_STALENESS_RULES:
            assert "local" in rule, f"Rule missing 'local' key: {rule}"
            assert "ok_zendesk" in rule, f"Rule missing 'ok_zendesk' key: {rule}"
            assert isinstance(rule["ok_zendesk"], list), (
                f"ok_zendesk must be a list: {rule}"
            )

    def test_default_rules_update_staleness_sets_stale_since(self) -> None:
        """update_staleness should set stale_since for a mismatched default rule."""
        card = _make_card(
            local_column="PR Submitted",
            zendesk_status="open",
            stale_since=None,
        )
        update_staleness(card, DEFAULT_STALENESS_RULES)
        assert card.stale_since is not None

    def test_default_rules_update_staleness_clears_on_match(self) -> None:
        """update_staleness should clear stale_since when status matches."""
        card = _make_card(
            local_column="Awaiting Close",
            zendesk_status="closed",
            stale_since=datetime.now(timezone.utc) - timedelta(hours=10),
        )
        update_staleness(card, DEFAULT_STALENESS_RULES)
        assert card.stale_since is None

    def test_default_rules_no_match_clears_staleness(self) -> None:
        """A column not in DEFAULT_STALENESS_RULES should clear stale_since."""
        card = _make_card(
            local_column="Triage",
            zendesk_status="open",
            stale_since=datetime.now(timezone.utc),
        )
        update_staleness(card, DEFAULT_STALENESS_RULES)
        assert card.stale_since is None
