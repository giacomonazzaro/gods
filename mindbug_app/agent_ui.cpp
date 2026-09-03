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
  Game_State& game    = static_cast<Game_State&>(game_abstract);
  auto&       table   = this->table;
  Choose      actions = choice.actions(game);

  if (this->gesture_map.empty()) {
    if (auto* options = std::get_if<Choose_Card>(&actions)) {
      for (int i = 0; i < (int)options->targets.size(); ++i) {
        auto card_id  = card_of_target(choice, options->targets[i]);
        auto action_id = i;  // The choice answers with the option's index.

        if (card_id == -1) {
          // No card: a hunt or block choice can offer to leave the decision
          // to the opponent, or let the attack through. Not a thing to
          // click, so it is a button instead, under the no-thing key.
          const char* label = choice.description == "hunt"
                               ? "Opponent chooses"
                               : "Don't block";
          this->gesture_map[-1].push_back(Gesture_Option{label, action_id});
          continue;
        }

        auto thing_id            = card_id;  // Cards assumed to have 1:1 mapping
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
          target_container_id == -1
            ? Play_Gesture{Gesture_Selection{action_id}}
            : Play_Gesture{Gesture_Drag_And_Drop{target_container_id, action_id}}
        };
      }
    } else if (auto* options = std::get_if<Choose_Option>(&actions)) {
      // The Mindbug decision is the only choice that isn't about a card.
      for (int i = 0; i < (int)options->targets.size(); ++i) {
        this->gesture_map[-1].push_back(Gesture_Option{options->targets[i], i});
      }
    } else if (auto* multi = std::get_if<Choose_Cards>(&actions)) {
      // Choose_Cards is never a "turn" choice, so a target is already a card
      // id (unlike Choose_Card, which can pack one, see card_of_target).
      auto targets =
        std::vector<int>(multi->targets.begin(), multi->targets.end());
      for (int target : targets) {
        this->gesture_map[target].push_back(
          Gesture_Multi_Select{multi->count, multi->up_to}
        );
      }

      int  count  = multi->count;
      bool up_to  = multi->up_to;
      this->resolve_multi_selection =
        [targets, count, up_to](const std::vector<int>& picked) -> int {
        // A combination lists its targets in the order `targets` has them,
        // so the picks have to go in that order too — neither the order
        // they were clicked in nor a sorted one.
        auto ordered_picked = std::vector<int>();
        for (int target : targets) {
          if (std::find(picked.begin(), picked.end(), target) != picked.end())
            ordered_picked.push_back(target);
        }
        std::vector<std::vector<int>> combinations =
          target_combinations(targets, count, up_to);
        for (int i = 0; i < (int)combinations.size(); ++i) {
          if (combinations[i] == ordered_picked) return i;
        }
        return -1;
      };
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
    table.window_size().x / 2.0f - 300.0f,
    16.0f,
    22,
    Color{255, 235, 150, 255}
  );

  // Every gesture (card, button, or multi-select) is handled by
  // process_gestures above, from the entries built at the top of this
  // function; there is nothing left to check this frame.
  return -1;
}
