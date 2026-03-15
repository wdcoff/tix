---
title: "fix: P2 code review findings — error handling, security, performance, architecture"
type: fix
status: active
date: 2026-03-15
---

# Fix P2 Code Review Findings

12 findings from the 6-agent code review, grouped into 4 parallel workstreams.

## Workstream A: Error handling + resilience (items 3, 4, 7)

**3. `_do_sync` only catches TixError** — `src/tix/app.py`
- Wrap the PR/deploy section in its own `try/except Exception` so a subprocess failure doesn't abort the entire sync after Zendesk data was already fetched.
- The outer catch should catch `Exception`, not just `TixError`, and notify the user.

**4. Bare `except Exception: pass` on ZendeskService init** — `src/tix/app.py`
- Replace `except Exception: pass` with `except Exception as e: self.notify(f"Zendesk init failed: {e}", severity="warning")` so config bugs are visible.

**7. `assert` used for runtime checks** — `src/tix/app.py`
- Replace all `assert` statements with `if not ...: raise` or explicit guards. `assert` is stripped with `python -O`.

## Workstream B: Security hardening (items 5, 12, 13)

**5. Incomplete env var scrubbing** — `src/tix/services/worktree.py`, `terminal_launcher.py`
- Change `_clean_env()` to strip all vars matching common secret patterns: anything containing `TOKEN`, `SECRET`, `KEY`, `PASSWORD`, `CREDENTIAL`.
- For terminal launchers specifically, consider an allowlist approach (only pass PATH, HOME, SHELL, TERM, TERM_PROGRAM, USER, LANG, LC_*).

**12. Config file created without 0o600 permissions** — `src/tix/config.py`
- In `create_default_config()`, use `os.open()` with `0o600` mode instead of `Path.write_text()`.
- Add a startup check: if config file perms are not `0o600`, warn the user.

**13. `base_branch` and `merge_sha` not validated** — `src/tix/services/worktree.py`, `deploy_tracker.py`
- Validate `base_branch` with the same regex as `branch_name`: `^[a-zA-Z0-9._/-]+$`
- Validate `merge_sha` matches `^[0-9a-f]{7,40}$` before passing to `git tag --contains`
- Add `--` separator in `deploy_tracker.py`'s git command

## Workstream C: Architecture cleanup (items 9, 10, 14)

**9. Duplicated `_clean_env()`** — `worktree.py`, `terminal_launcher.py`
- Extract to `src/tix/services/_env.py` (or `src/tix/subprocess_utils.py`)
- Make it public: `clean_env()` not `_clean_env()`
- Update all imports in worktree, terminal_launcher, pr_tracker, deploy_tracker

**10. Module-level mutable `_last_tag_fetch` global** — `deploy_tracker.py`
- Convert `deploy_tracker` to a class `DeployTracker` that owns the timestamp
- Or: pass `last_fetch` as a parameter and return the updated value
- Simplest: make it a class with `__init__` storing the timestamp

**14. `app.py` is a God Object** — `src/tix/app.py`
- Extract `_do_sync` logic into a `SyncCoordinator` class in `src/tix/sync.py`
- `SyncCoordinator.__init__` takes ZendeskService, StateManager, config
- `SyncCoordinator.run_sync()` does the full pipeline: fetch → apply → archive → staleness → PR → deploy → save
- `TixApp` delegates to `SyncCoordinator` in the background worker

## Workstream D: Performance (item 11)

**11. Full widget teardown/remount on every board refresh** — `screens/board.py`, `widgets/column.py`
- Remove `_update_title()` call from inside `add_ticket()` — caller already calls it after populating
- Replace per-child `remove()` loop in `clear_tickets()` with batch `query(TicketCardWidget).remove()` or equivalent
- Consider diff-based refresh: only add/remove changed cards instead of full teardown

## Workstream E: State mutations bypass StateManager (item 8)

**8. Direct mutation of TicketData objects** — `app.py`, `staleness.py`
- Add methods to StateManager: `update_pr(ticket_id, PRContext)`, `mark_deployed(ticket_id, tag)`, `update_staleness_all(rules, warn_after_hours)`
- Route all mutations through these methods instead of directly mutating `ticket.pr`, `ticket.deployed_in_tag`, `ticket.stale_since`
- This enforces the single-writer pattern and makes mutations auditable

## Acceptance Criteria

- [ ] `_do_sync` catches `Exception` at the outer level, shows error via notify
- [ ] PR/deploy section has its own try/except so Zendesk sync data isn't lost on subprocess failure
- [ ] ZendeskService init failure shows a warning notification, not silent pass
- [ ] No `assert` statements remain in production code (app.py)
- [ ] `clean_env()` strips all vars matching TOKEN/SECRET/KEY/PASSWORD/CREDENTIAL patterns
- [ ] Terminal launchers use allowlist env for spawned terminal sessions
- [ ] Config file created with `0o600` permissions
- [ ] Startup warns if config file is world-readable
- [ ] `base_branch` validated with branch name regex
- [ ] `merge_sha` validated with hex regex before subprocess use
- [ ] `clean_env()` lives in one shared module, imported by all services
- [ ] `deploy_tracker` no longer uses module-level mutable global
- [ ] Sync logic extracted from TixApp into SyncCoordinator
- [ ] All state mutations route through StateManager methods
- [ ] `_update_title()` not called N times during board population
- [ ] Column clear uses batch removal instead of per-child loop
- [ ] All 98+ existing tests still pass
- [ ] New tests for: clean_env patterns, base_branch validation, merge_sha validation, SyncCoordinator

## Parallelization

Workstreams A-E are independent and can be executed by parallel agents:
- **A** (error handling): touches `app.py`
- **B** (security): touches `config.py`, `worktree.py`, `deploy_tracker.py`
- **C** (architecture): touches service imports, `deploy_tracker.py`, creates `sync.py`
- **D** (performance): touches `board.py`, `column.py`
- **E** (state): touches `state_manager.py`, `app.py`

Note: A, C, and E all touch `app.py`. Execute C first (extract SyncCoordinator), then A and E can work on the extracted `sync.py` and `state_manager.py` respectively without conflicts. So the execution order is: **B + C + D in parallel**, then **A + E in parallel**.
