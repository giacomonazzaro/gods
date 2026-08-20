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
  picked_card      = -1;
  picked_mode      = -1;
  picked_transport = -1;
}

int Air_Land_Sea_Agent_UI::choose_action(Game& game, const Choice& choice) {
  Game_State&  state   = static_cast<Game_State&>(game);
  Table_State& table   = this->table;
  const Input& input   = *this->input;
  Choose       actions = choice.actions(game);
  const auto   targets = targets_of(actions);

  // Every card and every theater starts plain; what the choice can take is
  // highlighted below.
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

  // The opponent's hand runs along the top edge, so the line sits on a dark
  // strip to stay readable over the cards.
  const std::string text  = instruction(choice);
  const float       width = (float)text_width(text, 20);
  const float       left  = (float)tt::WINDOW_WIDTH / 2.0f - width / 2.0f;
  DrawRectangle(
    (int)left - 16, 8, (int)width + 32, 34, ::Color{0, 0, 0, 200}
  );
  render_text(text, left, 16.0f, 20, Color{255, 235, 150, 255});

  // Buttons run up from the bottom-left corner, beside the player's hand.
  Rectangle button = place_on_screen(240, 46, "left", "bottom", 20);
  auto      next_button = [&button] { button.y -= button.height + 12.0f; };

  // ---- A turn: pick the card, then face up or face down, then the theater.
  if (choice.description == "turn") {
    int withdraw_index = -1;
    for (int i = 0; i < (int)targets.size(); ++i) {
      if (targets[i] == WITHDRAW_MOVE) withdraw_index = i;
    }
    if (withdraw_index != -1 && immediate_button(button, "Withdraw", input)) {
      reset();
      return withdraw_index;
    }
    next_button();

    if (picked_card == -1) {
      for (int target : targets) {
        if (target == WITHDRAW_MOVE) continue;
        const int card = move_card(target);
        highlight_card(card);
        if (thing_pressed(card, table, input)) picked_card = card;
      }
      return -1;
    }
    highlight_card(picked_card);

    if (immediate_button(button, "Cancel", input)) {
      reset();
      return -1;
    }
    next_button();

    if (picked_mode == -1) {
      bool face_up_possible   = false;
      bool face_down_possible = false;
      for (int target : targets) {
        if (target == WITHDRAW_MOVE || move_card(target) != picked_card)
          continue;
        if (move_face_down(target))
          face_down_possible = true;
        else
          face_up_possible = true;
      }
      if (face_down_possible &&
          immediate_button(button, "Play face down", input)) {
        picked_mode = 1;
      }
      next_button();
      if (face_up_possible && immediate_button(button, "Deploy face up", input))
        picked_mode = 0;
      return -1;
    }

    // Only the theaters this card may go to are left; one of them ends the
    // turn.
    auto matching = std::vector<int>();
    for (int i = 0; i < (int)targets.size(); ++i) {
      if (targets[i] == WITHDRAW_MOVE) continue;
      if (move_card(targets[i]) != picked_card) continue;
      if (move_face_down(targets[i]) != (picked_mode == 1)) continue;
      matching.push_back(i);
    }
    if (matching.size() == 1) {
      reset();
      return matching[0];
    }
    for (int index : matching) {
      const int position = move_position(targets[index]);
      highlight_theater(position);
      if (thing_pressed(theater_bar_thing(position), table, input)) {
        reset();
        return index;
      }
    }
    return -1;
  }

  // ---- Reinforce: the top card of the deck goes into a theater, or nowhere.
  if (choice.description == "reinforce") {
    if (!state.deck.empty()) {
      const int         top  = state.deck.front();
      const std::string name = std::string("Top of the deck: ") +
                               card_designs[top].name + " (" +
                               theater_name(card_theater(top)) + " " +
                               std::to_string(card_strength(top)) + ")";
      render_text(
        name,
        (float)tt::WINDOW_WIDTH / 2.0f - (float)text_width(name, 18) / 2.0f,
        44.0f,
        18,
        Color{255, 235, 150, 255}
      );
    }
    for (int i = 0; i < (int)targets.size(); ++i) {
      if (targets[i] == DECLINE) {
        if (immediate_button(button, "Don't play it", input)) return i;
        next_button();
        continue;
      }
      highlight_theater(targets[i]);
      if (thing_pressed(theater_bar_thing(targets[i]), table, input)) return i;
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
  for (int i = 0; i < (int)targets.size(); ++i) {
    if (targets[i] == DECLINE) {
      if (immediate_button(button, "Skip", input)) return i;
      next_button();
      continue;
    }
    highlight_card(targets[i]);
    if (thing_pressed(targets[i], table, input)) return i;
  }
  return -1;
}
