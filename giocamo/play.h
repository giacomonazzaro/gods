#pragma once

#include <game/agent.h>
#include <giocamo/online/online.h>
#include <struct/json.h>
#include <tabletop/input_recorder.h>
#include <tabletop/rendering.h>  // for highlight_thing_border()
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>

#include <algorithm>
#include <functional>
#include <nlohmann/json.hpp>
#include <optional>
#include <variant>

#include "menu.h"
#include "undo.h"

// SPACE-to-zoom: zooms the thing under the cursor while SPACE is held,
// clears the zoom otherwise. tabletop's process_input also handles this
// internally; calling both is harmless (idempotent).
void update_zoomed_thing(Table_State& table_state, const Input& input);

// Resolve the play mode in priority order:
//   1. `--local-host` / `--local-join` on argv → loopback handshake; no menu.
//   2. `skip_menu == true` → default Menu_Result (mode = VS_AI, no online).
//   3. Otherwise opens the menu and returns the user's choice.
// The returned Menu_Result owns its `online` field (valid only when
// mode == ONLINE). `cli_seed` is folded into the result's seed for solo
// play; online uses the matchmaker's seed instead.
Menu_Result run_menu(
  const std::string&               title,
  Vector2                          window_size,
  Input_Feed&                      inputs,
  std::optional<Online_Connection> local_connection,
  bool                             skip_menu,
  int                              cli_seed
);

// Wrap a local Agent into the right duel for the chosen mode:
//   - ONLINE: pairs `local_agent` with an Agent_Remote (via make_online_duel).
//   - Otherwise: returns Agent_Duel(local_agent, opponent, /*swap=*/seat1).
// For hot-seat callers pass `opponent == local_agent`; for vs-AI pass the
// already-built AI agent (caller decides any Agent_Async wrapping).
Agent* make_duel(
  Agent* local_agent, Agent* opponent, const Menu_Result& menu_result
);

// Parsed command-line options shared by every game app.
//   --hot-seat        → vs_ai=false, skip_menu=true (one screen, two players).
//   --skip-menu       → skip the menu, default to vs-AI.
//   --seed=N          → deterministic deal for solo play. When omitted, the
//                       parser generates a random seed so the field always has
//                       a value.
//   --record=PATH     → play live and write the input stream to PATH.
//   --playback=PATH   → replay the input stream in PATH instead of the mouse.
//   --load[=PATH]     → start from the game saved on disk, not from a deal.
//                       Without a path the game reads its usual one.
struct Play_Options {
  bool        vs_ai      = true;
  bool        skip_menu  = false;
  int         seed       = 0;
  Input_Mode  input_mode = Input_Mode::Live;
  std::string input_file_path;  // Where to write it, or where to read it.
  bool        load_from_disk = false;
  std::string load_path      = "data/debug_game_state.json";

  // --local-host / --local-join.
  std::optional<Online_Connection> local_connection;
};
Play_Options parse_play_args(int argc, char** argv);

// Wrap the AI in Agent_Async when playing vs the computer, then build the duel
// for the current play mode. For hot-seat, pass `local_agent` itself as the
// opponent (it plays both seats).
Agent* make_agent_pair(
  Agent*             local_agent,
  Agent*             ai_opponent,
  const Menu_Result& menu_result,
  bool               vs_ai
);
#include <struct/print.h>

// A button not tied to any thing on the table (e.g. "Don't block"). Stored
// under gesture_map key -1, since it has no thing of its own.
struct Gesture_Option {
  std::string label;
  int         action_index;
};

// Click the thing (the map's key) to select it, then confirm with Done.
struct Gesture_Selection {
  int action_index;
};

// Drag the thing (the map's key) and drop it onto container_id.
struct Gesture_Drag_And_Drop {
  int container_id;  // where the thing is dropped
  int action_index;
};

// One of several things that can be clicked in and out of a running
// selection, confirmed once enough are picked. count/up_to are the same on
// every thing offering this gesture for a given choice — they describe the
// whole selection, not this one thing.
struct Gesture_Multi_Select {
  int  count;   // how many things the choice wants.
  bool up_to;   // pick up to count, instead of exactly count.
};

using Play_Gesture = std::variant<
  Gesture_Option, Gesture_Selection, Gesture_Drag_And_Drop,
  Gesture_Multi_Select>;

struct Agent_UI : Agent {
  Table_State table;
  // The frame being drawn, so choose_action can read the mouse. The loop sets
  // it before asking the agent for a move.
  const Input*                                       input = nullptr;
  std::unordered_map<int, std::vector<Play_Gesture>> gesture_map;

  // Where process_gestures draws Done/Option/Confirm buttons. Defaults to the
  // right edge, under the score line; a game with a different button rail
  // overrides it (see Agent_UI's constructor).
  Rectangle button_anchor = place_on_screen(200, 46, "right", "center", 24);

  // A thing clicked to start a Gesture_Selection, waiting for the Done
  // button to confirm it. -1 when nothing is selected.
  int selected_thing_id = -1;

  // Things picked so far for a Gesture_Multi_Select.
  std::vector<int> multi_selection;
  // Turns the finished multi_selection into an action index — the mapping
  // from a set of things to an action index is the game's to define. Set by
  // the game alongside the Gesture_Multi_Select entries in gesture_map.
  std::function<int(const std::vector<int>& things)> resolve_multi_selection;

  // Called after undo/redo (see play.cpp) and whenever a search agent would
  // drop its own cached state. gesture_map is built from the choice at hand
  // and selected_thing_id/multi_selection track picks made against it, so
  // once undo/redo swaps that choice out from under them, all three are
  // stale — a leftover gesture_map entry could still map a drag or a click to
  // an action index from the position that no longer exists. Clearing them
  // here makes choose_action rebuild fresh next frame.
  void reset() override {
    gesture_map.clear();
    selected_thing_id = -1;
    multi_selection.clear();
  }

  int process_gestures(
    const Drag_State& drag, const std::optional<Drop_Gesture>& drop
  ) {
    auto color = Color{255, 200, 0, 255};

    // Something is selected for a click gesture: show Done to confirm.
    // Clicking anything else (the same thing, another thing, empty space)
    // cancels the selection instead.
    if (selected_thing_id != -1) {
      auto selected_color = Color{0, 200, 255, 255};
      highlight_thing_border(table, selected_thing_id, selected_color);
      Rectangle button = button_anchor;
      if (immediate_button(button, "Done", *input)) {
        int action_index = -1;
        auto it = gesture_map.find(selected_thing_id);
        if (it != gesture_map.end()) {
          for (const Play_Gesture& gesture : it->second) {
            if (auto* selection = std::get_if<Gesture_Selection>(&gesture)) {
              action_index = selection->action_index;
            }
          }
        }
        selected_thing_id = -1;
        return action_index;
      }
      if (input->left_pressed) selected_thing_id = -1;
      return -1;
    }

    // Buttons not tied to any thing, drawn where every other button is.
    auto option_it = gesture_map.find(-1);
    if (option_it != gesture_map.end()) {
      Rectangle button = button_anchor;
      for (const Play_Gesture& gesture : option_it->second) {
        auto* option = std::get_if<Gesture_Option>(&gesture);
        if (!option) continue;
        if (immediate_button(button, option->label, *input)) {
          return option->action_index;
        }
        button.y += button.height + 14.0f;
      }
    }

    // Several things can be toggled into a selection, confirmed once enough
    // are picked.
    {
      int  multi_count = -1;
      bool multi_up_to = false;
      int  multi_total = 0;
      for (const auto& entry : gesture_map) {
        for (const Play_Gesture& gesture : entry.second) {
          auto* multi = std::get_if<Gesture_Multi_Select>(&gesture);
          if (!multi) continue;
          multi_count = multi->count;
          multi_up_to = multi->up_to;
          multi_total += 1;
        }
      }

      if (multi_count != -1) {
        auto picked_color = Color{0, 200, 255, 255};
        for (const auto& entry : gesture_map) {
          int thing_id = entry.first;
          bool has_multi = false;
          for (const Play_Gesture& gesture : entry.second) {
            if (std::holds_alternative<Gesture_Multi_Select>(gesture)) {
              has_multi = true;
            }
          }
          if (!has_multi) continue;

          bool picked = std::find(
                          multi_selection.begin(), multi_selection.end(),
                          thing_id
                        ) != multi_selection.end();
          highlight_thing_border(
            table, thing_id, picked ? picked_color : color
          );
          if (!picked && (int)multi_selection.size() < multi_count &&
              thing_pressed(thing_id, table, *input)) {
            multi_selection.push_back(thing_id);
          }
        }

        bool complete = multi_up_to ||
                        (int)multi_selection.size() == multi_count ||
                        (int)multi_selection.size() == multi_total;
        if (complete) {
          std::string label = "Confirm " +
                              std::to_string((int)multi_selection.size()) +
                              "/" + std::to_string(multi_count);
          Rectangle button = button_anchor;
          if (immediate_button(button, label, *input) &&
              resolve_multi_selection) {
            int action_index = resolve_multi_selection(multi_selection);
            multi_selection.clear();
            return action_index;
          }
        }
        return -1;
      }
    }

    if (drop) {
      print(*drop);

      // The drag is already cleared when the drop is recorded, so the thing
      // that was dropped is the one the drop names.
      // A thing with no gesture goes nowhere.
      auto it = gesture_map.find(drop->thing_id);
      if (it != gesture_map.end()) {
        for (const Play_Gesture& gesture : it->second) {
          auto* drag_and_drop = std::get_if<Gesture_Drag_And_Drop>(&gesture);
          if (drag_and_drop && drag_and_drop->container_id == drop->to_parent) {
            return drag_and_drop->action_index;
          }
        }
      }
    } else if (input->left_pressed) {
      // It's just click.
      float mx = (float)this->input->mouse_x;
      float my = (float)this->input->mouse_y;

      auto thing_location = find_thing_at(mx, my, table);
      if (thing_location.size()) {
        auto thing_id = thing_location.back();
        auto it       = gesture_map.find(thing_id);
        if (it != gesture_map.end()) {
          for (const Play_Gesture& gesture : it->second) {
            if (std::holds_alternative<Gesture_Selection>(gesture)) {
              selected_thing_id = thing_id;
              break;
            }
          }
        }
      }
    }

    // Show every thing a gesture can start from.
    for (const auto& entry : gesture_map) {
      highlight_thing_border(table, entry.first, color);
    }

    // A thing with no gesture goes nowhere.
    auto it = gesture_map.find(drag.thing_id());
    if (it == gesture_map.end()) return -1;

    for (const Play_Gesture& gesture : it->second) {
      auto* drag_and_drop = std::get_if<Gesture_Drag_And_Drop>(&gesture);
      if (!drag_and_drop) continue;  // Not a dragging gesture.

      // Highlight all possible drag options.
      // TODO: Fill the thing inside, not the border.
      brighten_thing(table, drag_and_drop->container_id, {30, 30, 0, 30});
      if (drag_and_drop->container_id == drag.hovered_id()) {
        highlight_thing_border(table, drag_and_drop->container_id, color);
      }
    }
    return -1;
  }
};

struct Giocamo {
  Game&        game;
  Agent_UI&    agent_ui;
  Table_State& table;

  int  bottom_player;
  bool hot_seat;

  Giocamo(Game& game, Agent_UI& agent_ui)
      : game(game), agent_ui(agent_ui), table(agent_ui.table) {}

  virtual ~Giocamo()                      = default;
  virtual void   init_table()             = 0;
  virtual void   update_table_from_game() = 0;
  virtual Agent* agent_opponent()         = 0;
  virtual void   update_game_from_table() = 0;
  // TODO(giacomo): Move to Game
  virtual std::vector<int> player_scores() const = 0;

  virtual Agent* agent_player() { return &agent_ui; }
  virtual void   on_message(const nlohmann::json& msg) {}

  // The agent that answers every seat. The default pairs the local player
  // with one opponent; a game with three or more seats overrides it and
  // builds an Agent_Seats of its own.
  virtual Agent* make_seat_agent(const Menu_Result& menu_result, bool vs_ai) {
    return make_agent_pair(
      agent_player(), agent_opponent(), menu_result, vs_ai
    );
  }

  // True when the lowest score wins, as in No Thanks!. The game-over screen
  // reads this to name the winner.
  virtual bool lower_score_wins() const { return false; }

  // Therse are implemented by Giocamo_With_History, no need to override.
  virtual void save_state() {}
  virtual bool undo() { return false; }
  virtual bool redo() { return false; }
  // The whole game state as JSON, and back. Online play sends this after
  // every move, and the receiving side reads it and lays the table out again.
  virtual std::string game_state_to_json() const { return ""; }
  virtual void        game_state_from_json(const std::string& json) {}
  virtual bool        draw_game_editor() { return false; }
  virtual bool        load_game(const std::string& path) { return false; }
};

// Standard game loop. Runs the menu, initializes the game with the seat's
// seed, lays the table out, then runs the table-top loop until the window
// closes.
void play_game(
  Giocamo& giocamo, Play_Options& options, const std::string& window_title
);

// A game derives from this instead of Giocamo directly to get undo. Copying a
// position needs the concrete game type, which is why this layer is a
// template — run_game still only ever sees Giocamo and calls the three hooks
// above.
template <typename Game_T>
struct Giocamo_With_History : Giocamo {
  using Giocamo::Giocamo;

  History<Game_T> history;

  Game_T&       typed_game() { return static_cast<Game_T&>(game); }
  const Game_T& typed_game() const { return static_cast<const Game_T&>(game); }

  void save_state() override { history.save(typed_game()); }

  std::string game_state_to_json() const override {
    return to_json(typed_game(), 0, /*pretty=*/false);
  }

  // The pending choice holds functions, which JSON cannot carry, so the game
  // works it out again from the state it just read, the same way load_game
  // does.
  void game_state_from_json(const std::string& json) override {
    auto received = Game_T();
    if (!from_json(json, received)) {
      std::cerr << "could not read the game state sent by the other player\n";
      return;
    }
    typed_game() = received;
    game.begin_game();
    update_table_from_game();
  }

  bool undo() override {
    if (!history.undo(typed_game())) return false;
    update_table_from_game();
    return true;
  }

  bool redo() override {
    if (!history.redo(typed_game())) return false;
    update_table_from_game();
    return true;
  }

  bool draw_game_editor() override {
    auto edited = draw_editor_ui(typed_game());
    if (edited) update_table_from_game();
    return edited;
  }

  // --load: carry on from the snapshot. The pending choice is worked out
  // again from the phase that was saved; effects that still owed a decision
  // are not in the snapshot, so those are lost.
  bool load_game(const std::string& path) override {
    try {
      typed_game() = load_from_json<Game_T>(path);
    } catch (const std::exception& error) {
      std::cerr << error.what() << "\n";
      return false;
    }
    game.begin_game();
    return true;
  }
};