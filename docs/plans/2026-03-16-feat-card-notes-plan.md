---
title: "feat: Add notes to ticket cards"
type: feat
status: active
date: 2026-03-16
---

# Add Notes to Ticket Cards

## Overview

Add a `notes` field to tickets so users can annotate cards with investigation context that isn't in Zendesk (local findings, next steps, hunches, etc.). Notes persist in `state.json`.

## Implementation

**1. Data model** — `src/tix/models.py`
- Add `notes: str | None = None` to `TicketData`
- Add to `to_dict()` / `from_dict()`

**2. Card badge** — `src/tix/widgets/card.py`
- In `_render_badges()`, if `ticket.notes` is truthy, prepend a `[dim]📝[/]` badge

**3. Note editing** — new keybinding `n`
- `src/tix/screens/board.py`: add `n` binding that opens a note editor modal for the focused card
- `src/tix/screens/note_editor.py` (new): `ModalScreen` with a `TextArea` widget pre-filled with existing note text. Enter saves (via callback), Escape cancels. Returns the note string.
- On save: update `ticket.notes` via StateManager, persist, refresh board

**4. StateManager** — `src/tix/state_manager.py`
- Add `update_notes(ticket_id: int, notes: str | None)` method

**5. Detail screen** — `src/tix/screens/ticket_detail.py`
- Show notes section if `ticket.notes` is set

**6. CSS** — `src/tix/css/app.tcss`
- Style the note editor modal (similar to ticket detail modal)

## Acceptance Criteria

- [ ] Press `n` on a card opens note editor modal
- [ ] Saving a note persists to state.json
- [ ] Cards with notes show 📝 badge
- [ ] Notes visible in detail screen (`d`)
- [ ] Empty note clears the field (no "empty string" stored)
- [ ] All tests pass
