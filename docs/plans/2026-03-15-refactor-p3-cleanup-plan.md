---
title: "refactor: P3 cleanup — dead code, naming, tests, logging"
type: refactor
status: completed
date: 2026-03-15
---

# P3 Cleanup

10 items, all independent. Execute in parallel.

## Group 1: Dead code removal (items 15, 19)

- **15. Delete unused functions**: `remove_worktree()`, `list_worktrees()` in worktree.py. `is_gh_available()` in pr_tracker.py. `check_staleness()` in staleness.py. Remove dead import of `is_gh_available` from app.py if still present.
- **19. Remove or use custom_status_map**: It's fetched and stored but never displayed. Either wire it into card display (show custom status label) or remove the fetch/storage entirely. Simplest: remove it — the raw zendesk_status string is sufficient.

## Group 2: Naming + docstring fixes (items 17, 20)

- **17. Fix CardMoveRight docstring**: Says "Shift+H" should say "Shift+L" in card.py.
- **20. Standardize card/ticket naming**: Rename `move_card` → `move_ticket`, `get_cards_by_column` → `get_tickets_by_column` in state_manager.py. Rename `card` parameter → `ticket` in staleness.py. Rename `card_widgets()` → `ticket_widgets()` in column.py. Update all callers.

## Group 3: Test improvements (items 16, 21)

- **16. Add missing tests**: Tests for `config.py` (load_config with valid/invalid TOML, env var handling, create_default_config). Tests for the `list_worktrees` porcelain parser (before deleting it — actually skip this since we're deleting it).
- **21. Replace manual try/except with pytest.raises**: In test_state_manager.py, the `test_move_nonexistent_ticket_raises` test uses manual try/except.

## Group 4: Operational improvements (items 22, 23, 24)

- **22. Add basic logging**: Add `import logging; logger = logging.getLogger(__name__)` to service modules. Log at INFO for sync events, WARNING for degraded features (gh missing, Zendesk unreachable), ERROR for failures. Configure in app.py to write to `~/.config/tix/tix.log`.
- **23. Clean up Warp launch config files**: After launching via Warp URI, schedule cleanup of the temp YAML file (delete after 5 seconds via threading.Timer or just on next launch).
- **24. Cap archived ticket list**: In state_manager.py, after archive_closed_tickets(), trim archived list to most recent 200 entries.

## Acceptance Criteria

- [ ] No unused functions remain (remove_worktree, list_worktrees, is_gh_available, check_staleness)
- [ ] custom_status_map either wired to display or removed
- [ ] CardMoveRight docstring says "Shift+L"
- [ ] Consistent "ticket" naming across state_manager, staleness, column
- [ ] config.py has test coverage
- [ ] Manual try/except replaced with pytest.raises
- [ ] Services log to tix.log
- [ ] Warp temp YAML cleaned up after launch
- [ ] Archived list capped at 200
- [ ] All tests pass
