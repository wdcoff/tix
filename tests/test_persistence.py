import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from tix.models import BoardState, Priority, TicketData
from tix.persistence import load_state, save_state


def _make_state() -> BoardState:
    return BoardState(
        tickets=[
            TicketData(
                ticket_id=100,
                subject="Test ticket",
                zendesk_status="open",
                local_column="Triage",
                priority=Priority.NORMAL,
                created_at=datetime(2025, 6, 1, 8, 0, 0, tzinfo=timezone.utc),
            ),
        ],
        last_sync=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestSaveLoadRoundTrip:
    def test_round_trip(self, tmp_path: Path):
        state_file = tmp_path / "state.json"
        original = _make_state()

        save_state(original, state_file)
        restored = load_state(state_file)

        assert len(restored.tickets) == 1
        assert restored.tickets[0].ticket_id == 100
        assert restored.tickets[0].subject == "Test ticket"
        assert restored.tickets[0].priority == Priority.NORMAL
        assert restored.tickets[0].created_at == datetime(2025, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
        assert restored.last_sync == original.last_sync

    def test_load_missing_file_returns_empty(self, tmp_path: Path):
        state_file = tmp_path / "does_not_exist.json"
        state = load_state(state_file)

        assert state.tickets == []
        assert state.archived == []
        assert state.last_sync is None

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        state_file = tmp_path / "nested" / "dir" / "state.json"
        save_state(BoardState(), state_file)

        assert state_file.exists()

    def test_saved_file_is_valid_json(self, tmp_path: Path):
        state_file = tmp_path / "state.json"
        save_state(_make_state(), state_file)

        with open(state_file) as f:
            data = json.load(f)

        assert "tickets" in data
        assert "last_sync" in data


class TestAtomicWrite:
    def test_file_permissions(self, tmp_path: Path):
        state_file = tmp_path / "state.json"
        save_state(_make_state(), state_file)

        file_stat = os.stat(state_file)
        mode = stat.S_IMODE(file_stat.st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_no_tmp_files_left_behind(self, tmp_path: Path):
        state_file = tmp_path / "state.json"
        save_state(_make_state(), state_file)

        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "state.json"
