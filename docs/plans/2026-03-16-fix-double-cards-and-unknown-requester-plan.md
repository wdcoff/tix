---
title: "fix: Double card count and unknown requester name"
type: fix
status: active
date: 2026-03-16
---

# Fix Double Card Count and Unknown Requester

## Bug 1: Each column shows double the number of cards

**Root cause:** `query(TicketCardWidget).remove()` in `clear_tickets()` is async — Textual schedules the removal but doesn't execute it immediately. When `_update_title()` and `add_ticket()` run right after, the old widgets are still in the DOM. So `_update_title()` counts old (pending removal) + new = exactly 2x.

**Fix:** Replace async `query().remove()` with synchronous per-widget removal, or skip counting widgets and track the count manually.

Simplest fix: track count as an integer instead of querying the DOM.

**Files:** `src/tix/widgets/column.py`

## Bug 2: Requester always shows "Unknown"

**Root cause:** Zendesk Search API returns `requester_id` (integer), not `requester_name`. The `apply_sync()` method reads `raw.get("requester_name")` which is always `None`. The Zendesk ticket object nests requester info under `via` or requires a sideload/separate lookup.

**Fix options:**
- **Option A (simple):** Use the Zendesk Search API with `include=users` sideload, which returns a `users` array alongside results. Match `requester_id` to the user list to get the name.
- **Option B (simpler):** The Zendesk search results include a `description` and `raw_subject` but for requester name, the ticket object from search actually does include a nested `requester` object when using the Tickets API (`/api/v2/tickets`), but NOT when using the Search API (`/api/v2/search`). With search, you only get `requester_id`.

**Recommended approach:** Add `&include=users` to the search query params. The response will include a top-level `users` array. Build a `{user_id: name}` lookup and pass it to `apply_sync()` to resolve requester names.

**Files:**
- `src/tix/services/zendesk.py` — add `include=users` param, return users alongside tickets
- `src/tix/sync.py` — pass user lookup to apply_sync
- `src/tix/state_manager.py` — accept user lookup in apply_sync, resolve requester_id → name

## Acceptance Criteria

- [ ] Each column shows the correct number of cards (not doubled)
- [ ] Requester name shows the actual Zendesk user name, not "Unknown"
- [ ] All tests pass
