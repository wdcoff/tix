from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class PRStatus(StrEnum):
    OPEN = "open"
    DRAFT = "draft"
    MERGED = "merged"
    CLOSED = "closed"


def _datetime_to_str(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _str_to_datetime(s: str | None) -> datetime | None:
    if s is None:
        return None
    return datetime.fromisoformat(s)


def _path_to_str(p: Path | None) -> str | None:
    if p is None:
        return None
    return str(p)


def _str_to_path(s: str | None) -> Path | None:
    if s is None:
        return None
    return Path(s)


@dataclass
class GitContext:
    worktree_path: Path | None = None
    branch_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "worktree_path": _path_to_str(self.worktree_path),
            "branch_name": self.branch_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GitContext:
        return cls(
            worktree_path=_str_to_path(data.get("worktree_path")),
            branch_name=data.get("branch_name"),
        )


@dataclass
class PRContext:
    url: str | None = None
    status: PRStatus | None = None
    merge_sha: str | None = None
    number: int | None = None
    repo: str | None = None  # "owner/repo" format

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status.value if self.status is not None else None,
            "merge_sha": self.merge_sha,
            "number": self.number,
            "repo": self.repo,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PRContext:
        raw_status = data.get("status")
        return cls(
            url=data.get("url"),
            status=PRStatus(raw_status) if raw_status is not None else None,
            merge_sha=data.get("merge_sha"),
            number=data.get("number"),
            repo=data.get("repo"),
        )


@dataclass
class TicketData:
    ticket_id: int
    subject: str
    zendesk_status: str
    local_column: str
    priority: Priority | None = None
    requester_name: str | None = None
    git: GitContext = field(default_factory=GitContext)
    pr: PRContext = field(default_factory=PRContext)
    notes: str | None = None
    deployed_in_tag: str | None = None
    stale_since: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_synced_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "subject": self.subject,
            "zendesk_status": self.zendesk_status,
            "local_column": self.local_column,
            "priority": self.priority.value if self.priority is not None else None,
            "requester_name": self.requester_name,
            "notes": self.notes,
            "git": self.git.to_dict(),
            "pr": self.pr.to_dict(),
            "deployed_in_tag": self.deployed_in_tag,
            "stale_since": _datetime_to_str(self.stale_since),
            "created_at": _datetime_to_str(self.created_at),
            "updated_at": _datetime_to_str(self.updated_at),
            "last_synced_at": _datetime_to_str(self.last_synced_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TicketData:
        raw_priority = data.get("priority")
        return cls(
            ticket_id=data["ticket_id"],
            subject=data["subject"],
            zendesk_status=data["zendesk_status"],
            local_column=data["local_column"],
            priority=Priority(raw_priority) if raw_priority is not None else None,
            requester_name=data.get("requester_name"),
            notes=data.get("notes"),
            git=GitContext.from_dict(data.get("git", {})),
            pr=PRContext.from_dict(data.get("pr", {})),
            deployed_in_tag=data.get("deployed_in_tag"),
            stale_since=_str_to_datetime(data.get("stale_since")),
            created_at=_str_to_datetime(data.get("created_at")),
            updated_at=_str_to_datetime(data.get("updated_at")),
            last_synced_at=_str_to_datetime(data.get("last_synced_at")),
        )


@dataclass
class BoardState:
    tickets: list[TicketData] = field(default_factory=list)
    archived: list[TicketData] = field(default_factory=list)
    last_sync: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tickets": [t.to_dict() for t in self.tickets],
            "archived": [t.to_dict() for t in self.archived],
            "last_sync": _datetime_to_str(self.last_sync),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BoardState:
        return cls(
            tickets=[TicketData.from_dict(t) for t in data.get("tickets", [])],
            archived=[TicketData.from_dict(t) for t in data.get("archived", [])],
            last_sync=_str_to_datetime(data.get("last_sync")),
        )
