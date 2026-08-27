#include "agent_ui.h"

#include <mindbug/gameplay.h>
#include <tabletop/config.h>
#include <tabletop/rendering.h>

#include <algorithm>
#include <string>
#include <variant>

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

using namespace mindbug;

// The attacking creature, named so the defender knows what is coming.
static std::string attacker_name(const Game_State& game) {
  if (game.attacker == -1) return "";
  const int design = design_of(game.attacker);
  return card_designs[design].name + " (" +
         std::to_string(effective_power(game, game.attacker)) + ")";
}

// What the player is being asked, by the name the game gives the choice.
static std::string instruction(const Game_State& game, const Choice& choice) {
  if (choice.description == "turn")
    return "Play a card from your hand, or attack with a creature";
  if (choice.description == "mindbug")
    return "Use a Mindbug to take this creature?";
  if (choice.description == "block")
    return attacker_name(game) + " is attacking. Block it?";
  if (choice.description == "hunt")
    return attacker_name(game) +
           " is attacking. Choose the blocker, or leave the choice to the "
           "opponent";
  if (choice.description == "frenzy")
    return attacker_name(game) + " survived. Attack a second time?";
  if (choice.description == "defeat") return "Choose a creature to defeat";
  if (choice.description == "take-control")
    return "Choose a creature to take control of";
  if (choice.description == "discard") return "Choose cards to discard";
  if (choice.description == "play-from-discard")
    return "Play a card from a discard pile";
  return std::string(choice.text_description);
}

// The card on the table an action target stands for, or -1 when the target is
// "no creature" — the option to let an attack through.
static int card_of_target(const Choice& choice, int target) {
  if (choice.description == "turn") return unpack_turn_action(target).card;
  return target;
}

// The targets a Choose offers, in option order. A choice that offers no card
// targets at all — an option list — has none.
static std::vector<int> targets_of(const Choose& actions) {
  if (auto* single = std::get_if<Choose_Card>(&actions)) {
    return std::vector<int>(single->targets.begin(), single->targets.end());
  }
  if (auto* multiple = std::get_if<Choose_Cards>(&actions)) {
    return std::vector<int>(multiple->targets.begin(), multiple->targets.end());
  }
  return {};
}

// The cards the pending choice can take are outlined here, over the table, so
// the outline lasts only for the frame it is drawn in and nothing has to clear
// it again afterwards.
static const Color CHOICE_COLOR = {255, 215, 0, 230};
// The thing that has `thing_id` as a child, or -1 if none does (the root, or
// an id not on the table).
int parent_of(const Table_State& table, int thing_id) {
  for (int id = 0; id < (int)table.things.size(); ++id) {
    if (find(table.things[id].children(), thing_id) != -1) return id;
  }
  return -1;
}
int Mindbug_Agent_UI::choose_action(Game& game_abstract, const Choice& choice) {
  auto action_index = choose_action_internal(game_abstract, choice);
  if (action_index != -1) {
    this->gesture_map.clear();
  }
  return action_index;
}

int Mindbug_Agent_UI::choose_action_internal(
  Game& game_abstract, const Choice& choice
) {
  Game_State&  game    = static_cast<Game_State&>(game_abstract);
  auto&        table   = this->table;
  const Input& input   = *this->input;
  Choose       actions = choice.actions(game);

  if (this->gesture_map.empty()) {
    if (auto* options = std::get_if<Choose_Card>(&actions)) {
      for (int i = 0; i < (int)options->targets.size(); ++i) {
        auto card_id = card_of_target(choice, options->targets[i]);
        // No card: not a thing to click, answered by a button instead.
        if (card_id == -1) continue;
        auto thing_id  = card_id;  // Cards assumed to have 1:1 mapping
        auto action_id = i;  // The choice answers with the option's index.
        auto creature_container  = parent_of(table, thing_id);
        auto target_container_id = -1;
        if (choice.description == "turn" || choice.description == "block") {
          if (table.things[creature_container].name == "p0_creatures") {
            // It's attacking or blocking.
            target_container_id = find_thing(table, "p1_creatures");
          }
          if (table.things[creature_container].name == "p0_hand") {
            // Playing a creature.
            target_container_id = find_thing(table, "p0_creatures");
          }
        }

        this->gesture_map[thing_id] = {
          Play_Gesture{target_container_id, action_id}
        };
      }
    }
  }

  auto drag = table.drag_state;
  auto drop = table.poll_dropped_thing();

  {
    auto action_id = this->process_gestures(drag, drop);
    if (action_id != -1) {
      printf("action_id: %d\n", action_id);
      return action_id;
    }
  }

  render_text(
    instruction(game, choice),
    (float)tt::WINDOW_WIDTH / 2.0f - 300.0f,
    16.0f,
    22,
    Color{255, 235, 150, 255}
  );

  // Buttons run down the right-hand side, under the score line.
  Rectangle button = place_on_screen(200, 46, "right", "center", 24);

  // The Mindbug decision is the only choice that isn't about a card.
  if (auto* options = std::get_if<Choose_Option>(&actions)) {
    for (int i = 0; i < (int)options->targets.size(); ++i) {
      if (immediate_button(button, options->targets[i], input)) return i;
      button.y += button.height + 14.0f;
    }
    return -1;
  }

  // A hunt or block choice can offer a "no card" option: leave the decision
  // to the opponent, or let the attack through. Not a card to click, so it
  // gets a button instead.
  if (auto* options = std::get_if<Choose_Card>(&actions)) {
    for (int i = 0; i < (int)options->targets.size(); ++i) {
      if (card_of_target(choice, options->targets[i]) != -1) continue;
      const char* label = choice.description == "hunt" ? "Opponent chooses"
                                                        : "Don't block";
      if (immediate_button(button, label, input)) return i;
      button.y += button.height + 14.0f;
    }
  }

  std::vector<int> targets = targets_of(actions);

  // One target to pick: it can be dragged onto the container its gesture
  // names, or clicked where it lies.
  // if (std::holds_alternative<Choose_Card>(actions)) {
  //   if (auto drop = table.poll_dropped_thing()) {
  //     const int action_index = process_gestures(*drop);
  //     if (action_index != -1) return action_index;
  //   }
  //   for (int i = 0; i < (int)targets.size(); ++i) {
  //     const int card = card_of_target(choice, targets[i]);
  //     if (card == -1) {
  //       // A hunter leaves the choice to the defender; the defender lets the
  //       // attack through.
  //       const char* label = choice.description == "hunt" ? "Opponent chooses"
  //                                                        : "Don't block";
  //       if (immediate_button(button, label, input)) return i;
  //       continue;
  //     }
  //     highlight_thing_border(table, card, CHOICE_COLOR);
  //     if (thing_pressed(card, table, input)) return i;
  //   }
  //   return -1;
  // }

  // Several targets to pick: click to add to the selection, then confirm.
  // Any other kind of choice is one this agent does not answer: it says "not
  // yet" and the next frame asks again.
  const Choose_Cards* multiple_or_null = std::get_if<Choose_Cards>(&actions);
  if (!multiple_or_null) return -1;
  const Choose_Cards& multiple = *multiple_or_null;
  for (int target : targets) {
    const int  card   = card_of_target(choice, target);
    const bool picked = std::find(selection.begin(), selection.end(), target) !=
                        selection.end();
    if (!picked) highlight_thing_border(table, card, CHOICE_COLOR);
    if (!picked && (int)selection.size() < multiple.count &&
        thing_pressed(card, table, input)) {
      selection.push_back(target);
    }
  }

  const bool complete = multiple.up_to ||
                        (int)selection.size() == multiple.count ||
                        (int)selection.size() == (int)targets.size();
  if (!complete) return -1;

  const std::string label = "Confirm " + std::to_string((int)selection.size()) +
                            "/" + std::to_string(multiple.count);
  if (!immediate_button(button, label, input)) return -1;

  // Answer with the option holding exactly the picked targets. A combination
  // lists its targets in the order `targets` has them, so the picks go in that
  // order too — neither the order they were clicked in nor a sorted one.
  auto picked = std::vector<int>();
  for (int target : targets) {
    if (std::find(selection.begin(), selection.end(), target) !=
        selection.end())
      picked.push_back(target);
  }

  std::vector<std::vector<int>> combinations =
    target_combinations(targets, multiple.count, multiple.up_to);
  for (int i = 0; i < (int)combinations.size(); ++i) {
    if (combinations[i] != picked) continue;
    selection.clear();
    return i;
  }
  return -1;
}
