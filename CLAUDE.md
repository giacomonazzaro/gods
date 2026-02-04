# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
pip install raylib
python -m gods.main           # Terminal-based game
python -m gods_graphical.main # Graphical version with Raylib
```

## Code Style

- snake_case for variables and functions
- Snake_Case for classes (e.g., `Game_State`, `Agent_Terminal`)
- Use dataclasses for data structures
- Prefer functions over methods
- Use `from __future__ import annotations` for Python 3.9 compatibility
- Hardcoded constants go in `kitchen_table/config.py` in the `tweak` dictionary

## Architecture

This is "Gods", a deck-builder card game with two main packages:

### `gods/` - Game Logic
| Module | Responsibility |
|--------|----------------|
| `models.py` | Core dataclasses: `Card`, `Player`, `Game_State`, `Choice`, `Card_Id` |
| `game.py` | Game flow functions: `game_loop()`, `play_card()`, `pass_turn()`, scoring |
| `cards.py` | Card implementations - each card is a dataclass subclass with hooks |
| `setup.py` | Deck loading from `cards.json`, game initialization |
| `agents/` | Player controllers: `Agent_Terminal`, `Agent_MCTS`, `Agent_Random`, `Agent_Duel` |

### `kitchen_table/` - Raylib Rendering Framework
Generic card game visualization using `pyray` (from the `raylib` package, not `pyray` package).

| Module | Responsibility |
|--------|----------------|
| `config.py` | All tweakable constants (dimensions, colors, layout positions) |
| `models.py` | Rendering dataclasses: `Card`, `Stack`, `Table_State`, `Drag_State` |
| `rendering.py` | All Raylib drawing calls |
| `input.py` | Mouse/keyboard handling, drag-and-drop |
| `game_state.py` | Stack/card position management |

### `gods_graphical/` - Integration
Bridges `gods` game state with `kitchen_table` rendering. Maps gods cards to visual cards.

## Key Patterns

**Agent Pattern:** All player interaction goes through agents implementing `perform_action(state, choice)`. The game calls agents to resolve decisions; agents can be human (terminal input), AI (MCTS), or combined (Agent_Duel for human vs AI).

**Choice/Action_List:** When a player must decide (play card, select target), game creates a `Choice` with an `Action_List` and a `resolve` callback. The agent picks an option index, then `choice.resolve(state, choice, index)` executes it.

**Card Hooks:** Card effects use lifecycle methods on `Card` subclasses:
- `on_played(game, agent)` - When card is played from hand
- `on_pass(game, agent)` - When owner passes
- `on_turn_start/end(game, agent)` - Turn phases
- `eval_points(game, player_index)` - People card scoring conditions
- `power_modifier(game, card, power)` - Modify other cards' power

**Card_Id:** Cards are referenced by location (`area`, `card_index`, `owner_index`) rather than by object, enabling state copying for AI search.

## Game Rules Reference

See `gods/rules.md` for card types (Wonder, Event, People), turn structure, and victory conditions.
