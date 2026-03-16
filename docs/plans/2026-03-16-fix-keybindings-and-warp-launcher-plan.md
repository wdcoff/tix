---
title: "fix: Shift+H/L keybindings and Warp terminal launcher"
type: fix
status: completed
date: 2026-03-16
---

# Fix Shift+H/L Keybindings and Warp Terminal Launcher

## Fix 1: Shift+H/L keybindings broken in Textual 3.x

**Bug:** `key_H` and `key_L` don't fire for Shift+H/Shift+L in Textual 3.x. The correct method names are `key_upper_h` and `key_upper_l`.

**Files:** `src/tix/widgets/card.py`

**Change:** Rename `key_H` → `key_upper_h`, `key_L` → `key_upper_l`

## Fix 2: Warp launcher — hybrid URI + keystroke approach

**Bug:** The YAML launch config approach doesn't reliably open tabs in the existing Warp window. The `activate` call spawns new windows.

**Fix:** Two-step hybrid:
1. `open warp://action/new_tab?path={abs_cwd}` — opens tab at correct CWD via Warp's official URI scheme
2. After a delay, use System Events keystroke to type and execute the command (`Popen`, fire-and-forget)

This replaces the YAML launch config approach entirely. Remove `_escape_yaml_value`, `_cleanup_file`, and the `threading` import since they're no longer needed.

**Files:** `src/tix/services/terminal_launcher.py`

## Acceptance Criteria

- [ ] Shift+H moves card left, Shift+L moves card right
- [ ] Enter on Warp opens a new tab in the existing window (not a new window)
- [ ] New tab CWD is the worktree path
- [ ] Claude Code command is typed and executed in the new tab
- [ ] All tests pass
