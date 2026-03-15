---
title: "fix: P1 staleness schema mismatch and terminal launcher injection"
type: fix
status: completed
date: 2026-03-15
---

# Fix P1: Staleness Schema Mismatch and Terminal Launcher Injection

## P1-1: Staleness rules schema mismatch

**Bug:** `config.py` defaults use keys `"column"` + `"warn_after_hours"` but `staleness.py` expects `"local"` + `"ok_zendesk"`. Staleness detection silently never fires. Tests mask this by defining their own compatible rules.

**Fix:** Align the config defaults to match what `staleness.py` expects. Update `DEFAULT_STALENESS_RULES` in `config.py` to use `"local"` and `"ok_zendesk"` keys. Also update `config.example.toml` and `create_default_config()` to match. Update the card widget to use staleness rules from config instead of hardcoding 24h.

**Files:**
- `src/tix/config.py` — fix `DEFAULT_STALENESS_RULES` schema
- `src/tix/widgets/card.py` — remove hardcoded 24h, use `stale_since` from data model
- `config.example.toml` — update staleness rule examples
- `tests/test_staleness.py` — add test using config-format rules to prevent regression

## P1-2: Command injection in terminal_launcher.py

**Bug:** AppleScript f-strings interpolate `cwd` and `command` without escaping. A double-quote in any path breaks out of the AppleScript string literal. Warp YAML uses f-string templating without proper escaping.

**Fix:**
- AppleScript: escape `"` → `\"` and `\` → `\\` in all interpolated values before embedding in AppleScript strings
- Warp YAML: use proper YAML escaping (quote strings, escape special chars) or `shlex.quote()` for the command portion
- Add `_escape_applescript(s: str) -> str` helper
- Add `_escape_yaml_value(s: str) -> str` helper

**Files:**
- `src/tix/services/terminal_launcher.py` — add escaping helpers, apply to all interpolation points
- `tests/test_terminal_launcher.py` — add tests for paths/commands containing quotes and special chars

## Acceptance Criteria

- [ ] Staleness detection fires correctly when using default config rules
- [ ] A config rule `{"local": "Needs Notify", "ok_zendesk": ["solved", "pending"]}` correctly flags a card with zendesk_status "open" as stale after configured hours
- [ ] Card widget reads `stale_since` from the data model instead of computing its own 24h check
- [ ] AppleScript strings properly escape `"` and `\` in cwd and command values
- [ ] Warp YAML properly escapes special characters in paths and commands
- [ ] Tests verify that paths containing `"`, `'`, `$`, spaces work correctly in all terminal launchers
- [ ] All 76+ existing tests still pass
