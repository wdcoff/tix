from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tix.models import BoardState, PRContext, Priority, TicketData
from tix.persistence import save_state
from tix.services.staleness import update_staleness


class StateManager:
    """Owns a BoardState and provides mutation operations.

    All changes go through this class so that invariants
    (e.g. local_column is never overwritten by a sync) are enforced.
    """

    def __init__(
        self,
        state: BoardState,
        state_path: Path | None = None,
        default_column: str = "Triage",
    ) -> None:
        self.state = state
        self.state_path = state_path
        self.default_column = default_column

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def _ticket_index(self) -> dict[int, TicketData]:
        return {t.ticket_id: t for t in self.state.tickets}

    def _archived_index(self) -> dict[int, TicketData]:
        return {t.ticket_id: t for t in self.state.archived}

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def apply_sync(
        self,
        tickets: list[dict[str, Any]],
        custom_status_map: dict[int, str] | None = None,
    ) -> None:
        """Merge Zendesk ticket data into local state.

        New tickets are placed in the default (first) column.
        Existing tickets have their Zendesk-sourced fields updated,
        but local_column is NEVER overwritten.
        Previously archived tickets that reappear as non-closed are
        restored to the default column.
        """
        now = datetime.now(timezone.utc)
        existing = self._ticket_index()
        archived = self._archived_index()

        if custom_status_map is not None:
            self.state.custom_status_map = custom_status_map

        status_map = self.state.custom_status_map

        for raw in tickets:
            tid = raw["id"]
            subject = raw.get("subject", "")
            # Resolve custom status label, fall back to stock status
            custom_status_id = raw.get("custom_status_id")
            if custom_status_id and custom_status_id in status_map:
                status = status_map[custom_status_id]
            else:
                status = raw.get("status", "open")
            priority_raw = raw.get("priority")
            requester = raw.get("requester_name")
            created = raw.get("created_at")
            updated = raw.get("updated_at")

            priority = Priority(priority_raw) if priority_raw in Priority.__members__.values() else None

            created_dt = (
                datetime.fromisoformat(created) if isinstance(created, str) else None
            )
            updated_dt = (
                datetime.fromisoformat(updated) if isinstance(updated, str) else None
            )

            if tid in existing:
                ticket = existing[tid]
                ticket.subject = subject
                ticket.zendesk_status = status
                ticket.priority = priority
                ticket.requester_name = requester
                ticket.created_at = created_dt
                ticket.updated_at = updated_dt
                ticket.last_synced_at = now
            elif tid in archived:
                # Ticket was previously archived -- check if it has reopened.
                if status not in ("solved", "closed"):
                    arch_ticket = archived[tid]
                    arch_ticket.subject = subject
                    arch_ticket.zendesk_status = status
                    arch_ticket.priority = priority
                    arch_ticket.requester_name = requester
                    arch_ticket.created_at = created_dt
                    arch_ticket.updated_at = updated_dt
                    arch_ticket.last_synced_at = now
                    arch_ticket.local_column = self.default_column
                    arch_ticket.stale_since = now
                    self.state.archived = [
                        t for t in self.state.archived if t.ticket_id != tid
                    ]
                    self.state.tickets.append(arch_ticket)
            else:
                ticket = TicketData(
                    ticket_id=tid,
                    subject=subject,
                    zendesk_status=status,
                    local_column=self.default_column,
                    priority=priority,
                    requester_name=requester,
                    created_at=created_dt,
                    updated_at=updated_dt,
                    last_synced_at=now,
                    stale_since=now,
                )
                self.state.tickets.append(ticket)

        self.state.last_sync = now

    # ------------------------------------------------------------------
    # Card movement
    # ------------------------------------------------------------------

    def move_card(self, ticket_id: int, target_column: str) -> None:
        """Move a ticket to a different column.

        Resets stale_since when the column actually changes.
        """
        for ticket in self.state.tickets:
            if ticket.ticket_id == ticket_id:
                if ticket.local_column != target_column:
                    ticket.local_column = target_column
                    ticket.stale_since = datetime.now(timezone.utc)
                return
        raise KeyError(f"Ticket {ticket_id} not found in active tickets")

    # ------------------------------------------------------------------
    # Column view
    # ------------------------------------------------------------------

    def get_cards_by_column(self) -> dict[str, list[TicketData]]:
        """Return active tickets grouped by their local_column."""
        result: dict[str, list[TicketData]] = {}
        for ticket in self.state.tickets:
            result.setdefault(ticket.local_column, []).append(ticket)
        return result

    # ------------------------------------------------------------------
    # Archival
    # ------------------------------------------------------------------

    def archive_closed_tickets(self) -> None:
        """Move tickets with zendesk_status in (solved, closed) to archived.

        If a previously archived ticket reappears as non-closed during
        a sync, apply_sync handles restoring it.
        """
        still_active: list[TicketData] = []
        for ticket in self.state.tickets:
            if ticket.zendesk_status in ("solved", "closed"):
                self.state.archived.append(ticket)
            else:
                still_active.append(ticket)
        self.state.tickets = still_active

        # Cap archived list to keep only the most recent entries
        MAX_ARCHIVED = 200
        if len(self.state.archived) > MAX_ARCHIVED:
            self.state.archived = self.state.archived[-MAX_ARCHIVED:]

    # ------------------------------------------------------------------
    # PR / deploy / staleness
    # ------------------------------------------------------------------

    def update_notes(self, ticket_id: int, notes: str | None) -> None:
        """Set or clear notes on a ticket. Empty string is treated as None."""
        for ticket in self.state.tickets:
            if ticket.ticket_id == ticket_id:
                ticket.notes = notes if notes and notes.strip() else None
                return
        raise KeyError(f"Ticket {ticket_id} not found in active tickets")

    def update_pr(self, ticket_id: int, pr_context: PRContext) -> None:
        """Set the PR context on a ticket."""
        for ticket in self.state.tickets:
            if ticket.ticket_id == ticket_id:
                ticket.pr = pr_context
                return
        raise KeyError(f"Ticket {ticket_id} not found in active tickets")

    def mark_deployed(self, ticket_id: int, tag: str) -> None:
        """Set deployed_in_tag on a ticket."""
        for ticket in self.state.tickets:
            if ticket.ticket_id == ticket_id:
                ticket.deployed_in_tag = tag
                return
        raise KeyError(f"Ticket {ticket_id} not found in active tickets")

    def update_staleness_all(
        self, rules: list[dict], warn_after_hours: int = 24
    ) -> None:
        """Run update_staleness on all active tickets."""
        for ticket in self.state.tickets:
            update_staleness(ticket, rules)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the current state to disk."""
        save_state(self.state, self.state_path)
