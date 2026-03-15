from datetime import datetime, timezone

from tix.models import BoardState, PRContext, PRStatus, Priority, TicketData
from tix.state_manager import StateManager


def _raw_ticket(tid: int, status: str = "open", **kwargs) -> dict:
    base = {
        "id": tid,
        "subject": f"Ticket {tid}",
        "status": status,
        "priority": "normal",
        "requester_name": "Bob",
        "created_at": "2025-06-01T08:00:00+00:00",
        "updated_at": "2025-06-01T10:00:00+00:00",
    }
    base.update(kwargs)
    return base


class TestApplySync:
    def test_new_tickets_added_to_default_column(self):
        mgr = StateManager(BoardState(), default_column="Triage")
        mgr.apply_sync([_raw_ticket(1), _raw_ticket(2)])

        assert len(mgr.state.tickets) == 2
        assert mgr.state.tickets[0].ticket_id == 1
        assert mgr.state.tickets[0].local_column == "Triage"
        assert mgr.state.tickets[1].ticket_id == 2

    def test_existing_ticket_updated_without_overwriting_column(self):
        existing = TicketData(
            ticket_id=1,
            subject="Old subject",
            zendesk_status="new",
            local_column="Investigating",
            priority=Priority.LOW,
        )
        state = BoardState(tickets=[existing])
        mgr = StateManager(state, default_column="Triage")

        mgr.apply_sync([_raw_ticket(1, subject="New subject", priority="normal")])

        ticket = mgr.state.tickets[0]
        assert ticket.subject == "New subject"
        assert ticket.priority == Priority.NORMAL
        assert ticket.local_column == "Investigating"  # NOT overwritten

    def test_sync_updates_last_sync(self):
        mgr = StateManager(BoardState())
        assert mgr.state.last_sync is None

        mgr.apply_sync([_raw_ticket(1)])
        assert mgr.state.last_sync is not None

    def test_sync_sets_last_synced_at_on_tickets(self):
        mgr = StateManager(BoardState())
        mgr.apply_sync([_raw_ticket(1)])

        assert mgr.state.tickets[0].last_synced_at is not None

    def test_custom_status_map_updated(self):
        mgr = StateManager(BoardState())
        mgr.apply_sync([], custom_status_map={10: "escalated"})

        assert mgr.state.custom_status_map == {10: "escalated"}

    def test_reopened_archived_ticket_restored(self):
        archived_ticket = TicketData(
            ticket_id=99,
            subject="Was closed",
            zendesk_status="closed",
            local_column="Done",
        )
        state = BoardState(archived=[archived_ticket])
        mgr = StateManager(state, default_column="Triage")

        mgr.apply_sync([_raw_ticket(99, status="open")])

        assert len(mgr.state.archived) == 0
        assert len(mgr.state.tickets) == 1
        assert mgr.state.tickets[0].ticket_id == 99
        assert mgr.state.tickets[0].local_column == "Triage"
        assert mgr.state.tickets[0].zendesk_status == "open"


class TestMoveCard:
    def test_move_changes_column(self):
        ticket = TicketData(
            ticket_id=1,
            subject="Test",
            zendesk_status="open",
            local_column="Triage",
        )
        mgr = StateManager(BoardState(tickets=[ticket]))
        mgr.move_card(1, "Investigating")

        assert mgr.state.tickets[0].local_column == "Investigating"

    def test_move_resets_stale_since(self):
        old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        ticket = TicketData(
            ticket_id=1,
            subject="Test",
            zendesk_status="open",
            local_column="Triage",
            stale_since=old_time,
        )
        mgr = StateManager(BoardState(tickets=[ticket]))
        mgr.move_card(1, "Investigating")

        assert mgr.state.tickets[0].stale_since is not None
        assert mgr.state.tickets[0].stale_since > old_time

    def test_move_to_same_column_does_not_reset_stale(self):
        old_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        ticket = TicketData(
            ticket_id=1,
            subject="Test",
            zendesk_status="open",
            local_column="Triage",
            stale_since=old_time,
        )
        mgr = StateManager(BoardState(tickets=[ticket]))
        mgr.move_card(1, "Triage")

        assert mgr.state.tickets[0].stale_since == old_time

    def test_move_nonexistent_ticket_raises(self):
        mgr = StateManager(BoardState())
        try:
            mgr.move_card(999, "Investigating")
            assert False, "Expected KeyError"
        except KeyError:
            pass


class TestArchiveClosedTickets:
    def test_solved_tickets_archived(self):
        tickets = [
            TicketData(ticket_id=1, subject="Open", zendesk_status="open", local_column="Triage"),
            TicketData(ticket_id=2, subject="Solved", zendesk_status="solved", local_column="Done"),
            TicketData(ticket_id=3, subject="Closed", zendesk_status="closed", local_column="Done"),
        ]
        mgr = StateManager(BoardState(tickets=tickets))
        mgr.archive_closed_tickets()

        assert len(mgr.state.tickets) == 1
        assert mgr.state.tickets[0].ticket_id == 1
        assert len(mgr.state.archived) == 2
        archived_ids = {t.ticket_id for t in mgr.state.archived}
        assert archived_ids == {2, 3}

    def test_no_closed_tickets_is_noop(self):
        tickets = [
            TicketData(ticket_id=1, subject="Open", zendesk_status="open", local_column="Triage"),
        ]
        mgr = StateManager(BoardState(tickets=tickets))
        mgr.archive_closed_tickets()

        assert len(mgr.state.tickets) == 1
        assert len(mgr.state.archived) == 0


class TestGetCardsByColumn:
    def test_groups_tickets(self):
        tickets = [
            TicketData(ticket_id=1, subject="A", zendesk_status="open", local_column="Triage"),
            TicketData(ticket_id=2, subject="B", zendesk_status="open", local_column="Investigating"),
            TicketData(ticket_id=3, subject="C", zendesk_status="open", local_column="Triage"),
        ]
        mgr = StateManager(BoardState(tickets=tickets))
        by_col = mgr.get_cards_by_column()

        assert len(by_col["Triage"]) == 2
        assert len(by_col["Investigating"]) == 1
        assert by_col["Investigating"][0].ticket_id == 2


class TestUpdatePr:
    def test_update_pr_sets_pr_context(self):
        ticket = TicketData(
            ticket_id=1,
            subject="Test",
            zendesk_status="open",
            local_column="Triage",
        )
        mgr = StateManager(BoardState(tickets=[ticket]))
        pr = PRContext(url="https://github.com/org/repo/pull/42", status=PRStatus.OPEN)

        mgr.update_pr(1, pr)

        assert mgr.state.tickets[0].pr.url == "https://github.com/org/repo/pull/42"
        assert mgr.state.tickets[0].pr.status == PRStatus.OPEN

    def test_update_pr_nonexistent_raises(self):
        mgr = StateManager(BoardState())
        try:
            mgr.update_pr(999, PRContext())
            assert False, "Expected KeyError"
        except KeyError:
            pass


class TestMarkDeployed:
    def test_mark_deployed_sets_tag(self):
        ticket = TicketData(
            ticket_id=1,
            subject="Test",
            zendesk_status="open",
            local_column="Triage",
        )
        mgr = StateManager(BoardState(tickets=[ticket]))

        mgr.mark_deployed(1, "v1.2.3")

        assert mgr.state.tickets[0].deployed_in_tag == "v1.2.3"

    def test_mark_deployed_nonexistent_raises(self):
        mgr = StateManager(BoardState())
        try:
            mgr.mark_deployed(999, "v1.0.0")
            assert False, "Expected KeyError"
        except KeyError:
            pass


class TestUpdateStalenessAll:
    def test_update_staleness_all_runs_on_all_tickets(self):
        """Tickets in a mismatched column get stale_since set; others get it cleared."""
        rules = [{"local": "Needs Notify", "ok_zendesk": ["solved", "pending"]}]
        tickets = [
            TicketData(
                ticket_id=1,
                subject="Mismatched",
                zendesk_status="open",
                local_column="Needs Notify",
            ),
            TicketData(
                ticket_id=2,
                subject="Matched",
                zendesk_status="solved",
                local_column="Needs Notify",
            ),
            TicketData(
                ticket_id=3,
                subject="No rule",
                zendesk_status="open",
                local_column="Triage",
            ),
        ]
        mgr = StateManager(BoardState(tickets=tickets))

        mgr.update_staleness_all(rules, warn_after_hours=24)

        # Ticket 1: mismatched, stale_since should be set
        assert mgr.state.tickets[0].stale_since is not None
        # Ticket 2: matched, stale_since should be None
        assert mgr.state.tickets[1].stale_since is None
        # Ticket 3: no rule, stale_since should be None
        assert mgr.state.tickets[2].stale_since is None
