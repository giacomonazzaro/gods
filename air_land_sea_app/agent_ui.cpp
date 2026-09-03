#include "agent_ui.h"

#include <air_land_sea/gameplay.h>
#include <tabletop/config.h>
#include <tabletop/rendering.h>

#include <string>
#include <variant>
#include <vector>

#include "ui.h"

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

using namespace air_land_sea;

// The Thing holding the theater card of a column. The three follow the cards
// of the deck, and main.cpp adds them in that order.
static int theater_bar_thing(int position) { return CARD_COUNT + position; }

// What the player is being asked, by the name the game gives the choice.
static std::string instruction(const Choice& choice) {
  if (choice.description == "turn")
    return "Play a card face up in its own theater, play one face down "
           "anywhere, or withdraw";
  if (choice.description == "maneuver")
    return "Maneuver: flip an uncovered card in a theater next to it";
  if (choice.description == "ambush")
    return "Ambush: flip an uncovered card in any theater";
  if (choice.description == "disrupt")
    return "Disrupt: flip one of your own uncovered cards";
  if (choice.description == "reinforce")
    return "Reinforce: play the top card of the deck face down in a theater "
           "next to it";
  if (choice.description == "transport")
    return "Transport: move one of your cards to another theater";
  if (choice.description == "redeploy")
    return "Redeploy: take one of your face-down cards back and play again";
  return std::string(choice.text_description);
}

static std::vector<int> targets_of(const Choose& actions) {
  const Choose_Card& single = std::get<Choose_Card>(actions);
  return std::vector<int>(single.targets.begin(), single.targets.end());
}

void Air_Land_Sea_Agent_UI::reset() {
  picked_transport = -1;
  // A card flipped in hand (see the "turn" handling below) is a stand-in for
  // the mode the player is about to drop it in, not a real game state — put
  // it back so a later hand doesn't inherit the flip.
  for (int card = 0; card < CARD_COUNT; ++card) {
    table.things[card].face_up = true;
  }
}

int Air_Land_Sea_Agent_UI::choose_action(Game& game, const Choice& choice) {
  auto action_index = choose_action_internal(game, choice);
  if (action_index != -1) {
    this->gesture_map.clear();
  }
  return action_index;
}

int Air_Land_Sea_Agent_UI::choose_action_internal(
  Game& game, const Choice& choice
) {
  Game_State&  state   = static_cast<Game_State&>(game);
  Table_State& table   = this->table;
  const Input& input   = *this->input;
  Choose       actions = choice.actions(game);
  const auto   targets = targets_of(actions);

  // Every card and every theater starts plain; what the choice can take is
  // highlighted below (by process_gestures for the choices it handles, by
  // highlight_card/highlight_theater for the multi-step ones it doesn't).
  for (int card = 0; card < CARD_COUNT; ++card) {
    table.draw_callbacks[card] =
      make_card_draw_callback(state, card, local_seat, hot_seat);
  }
  for (int position = 0; position < THEATER_COUNT; ++position) {
    table.draw_callbacks[theater_bar_thing(position)] =
      make_theater_draw_callback(state, position);
  }
  auto highlight_card = [&](int card) {
    table.draw_callbacks[card] =
      make_card_draw_callback(state, card, local_seat, hot_seat, true);
  };
  auto highlight_theater = [&](int position) {
    table.draw_callbacks[theater_bar_thing(position)] =
      make_theater_draw_callback(state, position, true);
  };

  // A turn: drag a card from hand onto a theater to play it. Face up is
  // legal only in the card's own theater (or with Air Drop / Aerodrome);
  // face down is legal anywhere. F flips the hovered or dragged card between
  // the two, which changes which theaters it can be dropped on. The legal
  // set depends on the flip, which can change every frame, so this map is
  // rebuilt every frame rather than cached like the others below.
  if (choice.description == "turn") {
    this->gesture_map.clear();
    int withdraw_index = -1;
    for (int i = 0; i < (int)targets.size(); ++i) {
      if (targets[i] == WITHDRAW_MOVE) {
        withdraw_index = i;
        continue;
      }
      const int  card      = move_card(targets[i]);
      const int  position  = move_position(targets[i]);
      const bool face_down = move_face_down(targets[i]);
      if (face_down != !table.things[card].face_up) continue;
      this->gesture_map[card].push_back(
        Gesture_Drag_And_Drop{theater_bar_thing(position), i}
      );
    }
    if (withdraw_index != -1) {
      this->gesture_map[-1].push_back(
        Gesture_Option{"Withdraw", withdraw_index}
      );
    }

    // A drop is legal exactly where the map above says it is.
    table.is_drop_allowed = [this](int, int hovered_id, int thing_id) {
      auto it = this->gesture_map.find(thing_id);
      if (it == this->gesture_map.end()) return false;
      for (const Play_Gesture& gesture : it->second) {
        auto* drag_and_drop = std::get_if<Gesture_Drag_And_Drop>(&gesture);
        if (drag_and_drop && drag_and_drop->container_id == hovered_id) {
          return true;
        }
      }
      return false;
    };

    int flip_target = table.drag_state.thing_id();
    if (flip_target < 0) {
      auto hovered =
        find_thing_at((float)input.mouse_x, (float)input.mouse_y, table);
      if (!hovered.empty()) flip_target = hovered.back();
    }
    if (key_pressed(input, KEY_F) && this->gesture_map.count(flip_target)) {
      table.things[flip_target].face_up = !table.things[flip_target].face_up;
    }

    auto drag       = table.drag_state;
    auto drop       = table.poll_dropped_thing();
    auto action_id  = this->process_gestures(drag, drop);
    if (action_id != -1) {
      reset();
      return action_id;
    }

    render_text(
      instruction(choice), 24.0f, 16.0f, 20, Color{255, 235, 150, 255}
    );
    return -1;
  }

  // Reinforce and every plain single-card choice (maneuver, ambush, disrupt,
  // redeploy, ...) are answered entirely by process_gestures: a
  // Gesture_Selection per legal target (click, then confirm with Done, so a
  // misclick doesn't resolve the choice), a Gesture_Option for a "decline"
  // target if there is one. "transport" picks a card and then a theater, so
  // it stays hand-written below — the map from thing clicked to action index
  // isn't known until both picks are in.
  if (this->gesture_map.empty() && choice.description != "transport") {
    for (int i = 0; i < (int)targets.size(); ++i) {
      if (targets[i] == DECLINE) {
        const char* label =
          choice.description == "reinforce" ? "Don't play it" : "Skip";
        this->gesture_map[-1].push_back(Gesture_Option{label, i});
        continue;
      }
      int thing_id = choice.description == "reinforce"
                       ? theater_bar_thing(targets[i])
                       : targets[i];
      this->gesture_map[thing_id].push_back(Gesture_Selection{i});
    }
  }

  if (!this->gesture_map.empty()) {
    auto drag = table.drag_state;
    auto drop = table.poll_dropped_thing();
    auto action_id = this->process_gestures(drag, drop);
    if (action_id != -1) return action_id;
  }

  // The opponent's hand runs along the top edge, so the line sits on a dark
  // strip to stay readable over the cards.
  const std::string text  = instruction(choice);
  const float       width = (float)text_width(text, 20);
  const float       left  = table.window_size().x / 2.0f - width / 2.0f;
  DrawRectangle(
    (int)left - 16, 8, (int)width + 32, 34, ::Color{0, 0, 0, 200}
  );
  render_text(text, left, 16.0f, 20, Color{255, 235, 150, 255});

  // Buttons run up from the bottom-left corner, beside the player's hand.
  Rectangle button = place_on_screen(240, 46, "left", "bottom", 20);
  auto      next_button = [&button] { button.y -= button.height + 12.0f; };

  // ---- Reinforce: the top card of the deck goes into a theater, or nowhere.
  // The theater/decline targets are already handled by process_gestures
  // above; only the "top of the deck" caption is drawn here.
  if (choice.description == "reinforce") {
    if (!state.deck.empty()) {
      const int         top  = state.deck.front();
      const std::string name = std::string("Top of the deck: ") +
                               card_designs[top].name + " (" +
                               theater_name(card_theater(top)) + " " +
                               std::to_string(card_strength(top)) + ")";
      render_text(
        name,
        table.window_size().x / 2.0f - (float)text_width(name, 18) / 2.0f,
        44.0f,
        18,
        Color{255, 235, 150, 255}
      );
    }
    return -1;
  }

  // ---- Transport: pick one of your cards, then the theater it moves to.
  if (choice.description == "transport") {
    for (int i = 0; i < (int)targets.size(); ++i) {
      if (targets[i] != DECLINE) continue;
      if (immediate_button(button, "Don't move anything", input)) {
        reset();
        return i;
      }
      next_button();
    }

    if (picked_transport == -1) {
      for (int target : targets) {
        if (target == DECLINE) continue;
        const int card = transport_card(target);
        highlight_card(card);
        if (thing_pressed(card, table, input)) picked_transport = card;
      }
      return -1;
    }
    highlight_card(picked_transport);
    for (int i = 0; i < (int)targets.size(); ++i) {
      if (targets[i] == DECLINE) continue;
      if (transport_card(targets[i]) != picked_transport) continue;
      const int position = transport_position(targets[i]);
      highlight_theater(position);
      if (thing_pressed(theater_bar_thing(position), table, input)) {
        reset();
        return i;
      }
    }
    return -1;
  }

  // ---- Every other choice is a single card, sometimes with a way out.
  // Already handled by process_gestures above.
  return -1;
}
