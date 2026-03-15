from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from tix.models import BoardState

DEFAULT_STATE_DIR = Path("~/.config/tix").expanduser()
DEFAULT_STATE_PATH = DEFAULT_STATE_DIR / "state.json"


def load_state(path: Path | None = None) -> BoardState:
    """Load board state from a JSON file.

    Returns an empty BoardState if the file does not exist.
    """
    state_path = path or DEFAULT_STATE_PATH

    if not state_path.exists():
        return BoardState()

    with open(state_path, "r") as f:
        data = json.load(f)

    return BoardState.from_dict(data)


def save_state(state: BoardState, path: Path | None = None) -> None:
    """Persist board state to a JSON file atomically.

    Writes to a temporary file with 0o600 permissions, then renames
    it into place so readers never see a partial write.
    """
    state_path = path or DEFAULT_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)

    data = state.to_dict()

    fd, tmp_path = tempfile.mkstemp(
        dir=state_path.parent,
        prefix=".tix_state_",
        suffix=".tmp",
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.rename(tmp_path, state_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
