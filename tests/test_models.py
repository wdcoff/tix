from datetime import datetime, timezone
from pathlib import Path

from tix.models import (
    BoardState,
    GitContext,
    PRContext,
    PRStatus,
    Priority,
    TicketData,
)


def _make_ticket(**overrides) -> TicketData:
    defaults = dict(
        ticket_id=12345,
        subject="Login broken for SSO users",
        zendesk_status="open",
        local_column="Triage",
        priority=Priority.HIGH,
        requester_name="Alice",
        git=GitContext(
            worktree_path=Path("/tmp/wt/ticket-12345"),
            branch_name="fix/ticket-12345",
        ),
        pr=PRContext(
            url="https://github.com/org/repo/pull/99",
            status=PRStatus.OPEN,
            merge_sha="abc123",
        ),
        deployed_in_tag="v1.2.3",
        stale_since=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        created_at=datetime(2025, 5, 30, 8, 0, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        last_synced_at=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return TicketData(**defaults)


class TestTicketDataRoundTrip:
    def test_full_ticket_round_trip(self):
        original = _make_ticket()
        data = original.to_dict()
        restored = TicketData.from_dict(data)

        assert restored.ticket_id == original.ticket_id
        assert restored.subject == original.subject
        assert restored.zendesk_status == original.zendesk_status
        assert restored.local_column == original.local_column
        assert restored.priority == original.priority
        assert restored.requester_name == original.requester_name
        assert restored.git.worktree_path == original.git.worktree_path
        assert restored.git.branch_name == original.git.branch_name
        assert restored.pr.url == original.pr.url
        assert restored.pr.status == original.pr.status
        assert restored.pr.merge_sha == original.pr.merge_sha
        assert restored.deployed_in_tag == original.deployed_in_tag
        assert restored.stale_since == original.stale_since
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at
        assert restored.last_synced_at == original.last_synced_at

    def test_ticket_with_none_fields(self):
        original = TicketData(
            ticket_id=1,
            subject="Minimal",
            zendesk_status="new",
            local_column="Triage",
        )
        data = original.to_dict()
        restored = TicketData.from_dict(data)

        assert restored.priority is None
        assert restored.requester_name is None
        assert restored.git.worktree_path is None
        assert restored.git.branch_name is None
        assert restored.pr.url is None
        assert restored.pr.status is None
        assert restored.stale_since is None
        assert restored.created_at is None

    def test_dict_contains_expected_types(self):
        ticket = _make_ticket()
        data = ticket.to_dict()

        assert isinstance(data["priority"], str)
        assert data["priority"] == "high"
        assert isinstance(data["git"]["worktree_path"], str)
        assert isinstance(data["pr"]["status"], str)
        assert isinstance(data["created_at"], str)


class TestBoardStateRoundTrip:
    def test_board_state_round_trip(self):
        original = BoardState(
            tickets=[_make_ticket(ticket_id=1), _make_ticket(ticket_id=2)],
            archived=[_make_ticket(ticket_id=3, zendesk_status="closed")],
            last_sync=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        data = original.to_dict()
        restored = BoardState.from_dict(data)

        assert len(restored.tickets) == 2
        assert restored.tickets[0].ticket_id == 1
        assert restored.tickets[1].ticket_id == 2
        assert len(restored.archived) == 1
        assert restored.archived[0].ticket_id == 3
        assert restored.last_sync == original.last_sync

    def test_empty_board_state_round_trip(self):
        original = BoardState()
        data = original.to_dict()
        restored = BoardState.from_dict(data)

        assert restored.tickets == []
        assert restored.archived == []
        assert restored.last_sync is None
