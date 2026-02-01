# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
pip install raylib
python main.py
```

## Code Style

- snake_case for variables and functions
- Snake_Case for classes (e.g., `Game_State`, `Drag_State`)
- Use dataclasses for data structures
- Prefer functions over methods
- Use `from __future__ import annotations` for Python 3.9 compatibility
- Hardcoded constants go in the `tweak` dictionary in `config.py`

## Architecture

This is a deck-builder card game using Python and Raylib with clear separation of concerns:

**Data flow:** `main.py` → `input.py` (updates) → `game_state.py` (state changes) → `rendering.py` (draws)

| Module | Responsibility |
|--------|----------------|
| `config.py` | All tweakable constants (dimensions, colors, positions) |
| `models.py` | Dataclasses: `Card`, `Stack`, `Drag_State`, `Game_State` |
| `game_state.py` | State manipulation functions (draw, discard, shuffle) |
| `input.py` | Mouse/keyboard handling, drag-and-drop logic |
| `rendering.py` | All Raylib drawing calls |
| `main.py` | Window init and main loop |

**Key patterns:**
- Cards live in Stacks; dragging removes a card from its stack temporarily
- `update_card_positions()` recalculates card x/y based on stack spread values
- Drawing uses `pyray` (from the `raylib` package, not the `pyray` package)
