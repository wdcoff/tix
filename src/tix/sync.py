"""Sync orchestration extracted from TixApp.

SyncCoordinator is a plain synchronous class that runs the full
sync pipeline (Zendesk fetch, PR detection, deploy detection, etc.)
and returns a result tuple.  It is designed to be called from a
Textual ``@work(thread=True)`` worker.
"""
from __future__ import annotations

import logging

from tix.config import Config
from tix.models import PRStatus
from tix.services.deploy_tracker import DeployTracker
from tix.services.pr_tracker import check_all_prs
from tix.state_manager import StateManager

# Type alias to keep import lightweight -- ZendeskService is only
# constructed inside TixApp when config is present.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tix.services.zendesk import ZendeskService

logger = logging.getLogger(__name__)


class SyncCoordinator:
    """Run the full sync pipeline.  All methods are synchronous."""

    def __init__(
        self,
        zendesk_service: ZendeskService,
        state_manager: StateManager,
        deploy_tracker: DeployTracker,
        config: Config,
        *,
        gh_available: bool = False,
    ) -> None:
        self._zendesk = zendesk_service
        self._manager = state_manager
        self._deploy_tracker = deploy_tracker
        self._config = config
        self._gh_available = gh_available
        self._custom_statuses_fetched = False

    def run_sync(self) -> tuple[int, str | None]:
        """Run full sync pipeline.

        Returns ``(ticket_count, error_message_or_none)``.
        """
        logger.info("Sync started")
        try:
            # 1. Fetch tickets from Zendesk
            tickets = self._zendesk.fetch_open_tickets()

            # 2. Fetch custom statuses (if not cached)
            custom_statuses = None
            if not self._custom_statuses_fetched:
                custom_statuses = self._zendesk.fetch_custom_statuses()
                self._custom_statuses_fetched = True

            # 3. Apply sync to state
            self._manager.apply_sync(tickets, custom_statuses)

            # 4. Archive closed tickets
            self._manager.archive_closed_tickets()

            # 5. Update staleness on all tickets
            self._manager.update_staleness_all(
                self._config.staleness_rules,
                self._config.warn_after_hours,
            )

            # 6-7. Check PRs and deploys (if gh available)
            # Wrapped separately so a subprocess failure doesn't lose
            # the Zendesk data that was already fetched and applied.
            pr_error: str | None = None
            try:
                if self._gh_available:
                    branch_names = [
                        ticket.git.branch_name
                        for ticket in self._manager.state.tickets
                        if ticket.git.branch_name
                    ]
                    if branch_names:
                        pr_map = check_all_prs(branch_names)
                        for ticket in self._manager.state.tickets:
                            bn = ticket.git.branch_name
                            if bn and bn in pr_map:
                                self._manager.update_pr(ticket.ticket_id, pr_map[bn])

                        # 7. Check deploys (for merged PRs)
                        merged_tickets = [
                            t for t in self._manager.state.tickets
                            if t.pr.status == PRStatus.MERGED
                            and t.pr.merge_sha
                            and not t.deployed_in_tag
                        ]
                        if merged_tickets:
                            self._deploy_tracker.maybe_fetch_tags(
                                self._config.repo_path
                            )
                            for ticket in merged_tickets:
                                if ticket.pr.merge_sha is None:
                                    continue
                                tag = self._deploy_tracker.check_deploy(
                                    self._config.repo_path, ticket.pr.merge_sha
                                )
                                if tag:
                                    self._manager.mark_deployed(ticket.ticket_id, tag)
            except Exception as exc:
                pr_error = f"PR/deploy check failed: {exc}"
                logger.warning("PR/deploy check failed: %s", exc)

            # 8. Save state
            self._manager.save()

            ticket_count = len(self._manager.state.tickets)
            logger.info("Sync complete: %d tickets", ticket_count)
            return ticket_count, pr_error

        except Exception as exc:
            error_msg = f"Sync failed: {exc}"
            if self._manager.state.tickets:
                error_msg += " (showing cached data)"
            logger.warning("Sync failed: %s", exc)
            return len(self._manager.state.tickets), error_msg
