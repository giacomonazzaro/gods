#include "cards.h"

#include <mindbug/gameplay.h>

#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>

namespace mindbug {

std::vector<Card_Design> card_designs;
std::vector<uint8_t>     all_cards;

static int parse_keyword(const std::string& name) {
  if (name == "sneaky") return SNEAKY;
  if (name == "hunter") return HUNTER;
  if (name == "frenzy") return FRENZY;
  if (name == "poisonous") return POISONOUS;
  if (name == "tough") return TOUGH;
  std::cerr << "mindbug: unknown keyword " << name << "\n";
  return 0;
}

bool load_card_designs(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    std::cerr << "mindbug: could not open " << path << "\n";
    return false;
  }
  nlohmann::json data;
  try {
    file >> data;
  } catch (const std::exception& error) {
    std::cerr << "mindbug: could not parse " << path << ": " << error.what()
              << "\n";
    return false;
  }
  if (!data.is_array() || data.size() != DESIGN_COUNT) {
    std::cerr << "mindbug: " << path << " must hold " << (int)DESIGN_COUNT
              << " cards\n";
    return false;
  }

  card_designs.clear();
  for (const auto& entry : data) {
    auto design     = Card_Design();
    design.name     = entry.value("name", std::string());
    design.text     = entry.value("text", std::string());
    design.image    = entry.value("image", std::string());
    design.power    = entry.value("power", 0);
    design.copies   = entry.value("copies", 1);
    design.keywords = 0;
    for (const auto& keyword : entry["keywords"]) {
      design.keywords |= parse_keyword(keyword.get<std::string>());
    }
    card_designs.push_back(design);
  }

  // The deck itself: one card per printed copy, so a design with two copies
  // becomes two separate cards that can be told apart by index.
  all_cards.clear();
  for (int design = 0; design < (int)card_designs.size(); ++design) {
    for (int copy = 0; copy < card_designs[design].copies; ++copy) {
      all_cards.push_back((uint8_t)design);
    }
  }
  return true;
}

// ---- Effect helpers ----

// Every card of a pile, as choice targets.
template <int N>
static Targets cards_of(const Array_Inline<uint8_t, N>& pile) {
  auto cards = Targets();
  cards.assign(pile.begin(), pile.end());
  return cards;
}

static void discard_from_hand(
  Game_State& state, int player, const std::vector<int>& cards
) {
  for (int card : cards) {
    remove_card(state.players[player].hand, card);
    state.players[player].discard.push_back(card);
  }
  draw_back_up_to_hand_size(state);
}

// Play `card` out of `pile_owner`'s discard pile, under the control of
// `controller`.
static void play_from_discard(
  Game_State& state, int pile_owner, int controller, int card
) {
  remove_card(state.players[pile_owner].discard, card);
  enter_play(state, card, controller);
}

// A number in [0, bound). Only Strange Barrel needs this.
static int next_random(Game_State& state, int bound) {
  state.random_seed = state.random_seed * 1664525u + 1013904223u;
  return (int)((state.random_seed >> 16) % (unsigned int)bound);
}

// ---- Card abilities ----
//
// One struct per card that does something, holding every ability it has. A
// card with no struct here (there are 5) has none: dispatch() below falls
// back to Card_Effects, which answers every question with "nothing happens".
// A method a struct doesn't write is inherited from Card_Effects the same
// way. Adding or changing a card is adding or changing one struct; nothing
// outside this file reads these structs directly.

struct Card_Effects {
  static void on_play(Game_State& state, int card) {}
  static void on_attack(Game_State& state, int card) {}
  static void on_defeated(Game_State& state, int card, int controller) {}

  // Power/keywords this card adds to another creature on its own side.
  static int ally_power_bonus(
    const Game_State& state, int ally, bool its_turn
  ) {
    return 0;
  }
  static int ally_keywords(const Game_State& state, int ally, int card) {
    return 0;
  }

  // Power/keywords this card adds to itself.
  static int self_power_bonus(const Game_State& state, int card) { return 0; }
  static int self_keywords(const Game_State& state, int card) { return 0; }

  // Keywords this card copies from the enemy side.
  static int mirrored_keywords(const Game_State& state, int card) { return 0; }

  // Whether this card's own ability, or its presence as an ally, stops
  // `blocker` from blocking `attacker`.
  static bool self_block_prevented(
    const Game_State& state, int attacker, int blocker
  ) {
    return false;
  }
  static bool ally_block_prevented(
    const Game_State& state, int ally, int attacker, int blocker
  ) {
    return false;
  }

  // Whether this card, on the other side, switches a Play ability off.
  static bool suppresses_enemy_play_ability() { return false; }
};

struct Axolotl_Healer : Card_Effects {
  static void on_play(Game_State& state, int card) {
    state.players[controller_of(state, card)].life += 2;
  }
};

struct Bee_Bear : Card_Effects {
  static bool self_block_prevented(const Game_State& state, int, int blocker) {
    return effective_power(state, blocker) <= 6;
  }
};

struct Brain_Fly : Card_Effects {
  static void on_play(Game_State& state, int card) {
    const int me = controller_of(state, card);
    state.queue.push_back(make_choice(
      me,
      "take-control",
      [](Game_State& game) { return creature_targets(game, -1, 6, 99); },
      [me](Game_State& game, int target) { take_control(game, target, me); }
    ));
  }
};

struct Chameleon_Sniper : Card_Effects {
  static void on_attack(Game_State& state, int card) {
    lose_life(state, 1 - controller_of(state, card), 1);
  }
};

struct Compost_Dragon : Card_Effects {
  static void on_play(Game_State& state, int card) {
    const int me = controller_of(state, card);
    state.queue.push_back(make_choice(
      me,
      "play-from-discard",
      [me](Game_State& game) { return cards_of(game.players[me].discard); },
      [me](Game_State& game, int card) {
        play_from_discard(game, me, me, card);
      }
    ));
  }
};

struct Deathweaver : Card_Effects {
  static bool suppresses_enemy_play_ability() { return true; }
};

struct Elephantopus : Card_Effects {
  // Holds small blockers back on any attack from its side, not only its own.
  static bool ally_block_prevented(
    const Game_State& state, int, int, int blocker
  ) {
    return effective_power(state, blocker) <= 4;
  }
};

struct Explosive_Toad : Card_Effects {
  static void on_defeated(Game_State& state, int, int controller) {
    state.queue.push_back(make_choice(
      controller,
      "defeat",
      [](Game_State& game) { return creature_targets(game, -1, 0, 99); },
      [](Game_State& game, int target) { defeat_creature(game, target); }
    ));
  }
};

struct Ferret_Bomber : Card_Effects {
  static void on_play(Game_State& state, int card) {
    const int them = 1 - controller_of(state, card);
    state.queue.push_back(make_multi_choice(
      them,
      "discard",
      [them](Game_State& game) { return cards_of(game.players[them].hand); },
      2,
      false,
      [them](Game_State& game, const std::vector<int>& cards) {
        discard_from_hand(game, them, cards);
      }
    ));
  }
};

struct Giraffodile : Card_Effects {
  static void on_play(Game_State& state, int card) {
    Player& player = state.players[controller_of(state, card)];
    player.hand.append(player.discard.begin(), player.discard.end());
    player.discard.clear();
  }
};

struct Goblin_Werewolf : Card_Effects {
  static int self_power_bonus(const Game_State& state, int card) {
    return state.current_player == controller_of(state, card) ? 6 : 0;
  }
};

struct Grave_Robber : Card_Effects {
  static void on_play(Game_State& state, int card) {
    const int me   = controller_of(state, card);
    const int them = 1 - me;
    state.queue.push_back(make_choice(
      me,
      "play-from-discard",
      [them](Game_State& game) { return cards_of(game.players[them].discard); },
      [me, them](Game_State& game, int card) {
        play_from_discard(game, them, me, card);
      }
    ));
  }
};

struct Harpy_Mother : Card_Effects {
  static void on_defeated(Game_State& state, int, int controller) {
    const int me   = controller;
    const int them = 1 - me;
    state.queue.push_back(make_multi_choice(
      me,
      "take-control",
      [them](Game_State& game) { return creature_targets(game, them, 0, 5); },
      2,
      true,
      [me](Game_State& game, const std::vector<int>& targets) {
        for (int target : targets) take_control(game, target, me);
      }
    ));
  }
};

struct Kangasaurus_Rex : Card_Effects {
  static void on_play(Game_State& state, int card) {
    const int them = 1 - controller_of(state, card);
    // Snapshot first: defeating one creature can move the others around.
    auto victims = creature_targets(state, them, 0, 4);
    for (int victim : victims) defeat_creature(state, victim);
  }
};

struct Killer_Bee : Card_Effects {
  static void on_play(Game_State& state, int card) {
    lose_life(state, 1 - controller_of(state, card), 1);
  }
};

struct Lone_Yeti : Card_Effects {
  static int self_power_bonus(const Game_State& state, int card) {
    const int controller = controller_of(state, card);
    return state.players[controller].creatures.size() == 1 ? 5 : 0;
  }
  static int self_keywords(const Game_State& state, int card) {
    const int controller = controller_of(state, card);
    return state.players[controller].creatures.size() == 1 ? FRENZY : 0;
  }
};

struct Mysterious_Mermaid : Card_Effects {
  static void on_play(Game_State& state, int card) {
    const int me           = controller_of(state, card);
    state.players[me].life = state.players[1 - me].life;
  }
};

struct Shark_Dog : Card_Effects {
  static void on_attack(Game_State& state, int card) {
    const int me   = controller_of(state, card);
    const int them = 1 - me;
    state.queue.push_back(make_choice(
      me,
      "defeat",
      [them](Game_State& game) { return creature_targets(game, them, 6, 99); },
      [](Game_State& game, int target) { defeat_creature(game, target); }
    ));
  }
};

struct Sharky_Crab_Dog_Mummypus : Card_Effects {
  static int mirrored_keywords(const Game_State& state, int card) {
    const int controller = controller_of(state, card);
    int       keywords   = 0;
    for (int enemy : state.players[1 - controller].creatures) {
      keywords |= own_keywords(state, enemy) &
                  (HUNTER | SNEAKY | FRENZY | POISONOUS);
    }
    return keywords;
  }
};

struct Shield_Bugs : Card_Effects {
  static int ally_power_bonus(const Game_State&, int, bool) { return 1; }
};

struct Snail_Hydra : Card_Effects {
  static void on_attack(Game_State& state, int card) {
    const int me   = controller_of(state, card);
    const int them = 1 - me;
    if (creature_targets(state, me, 0, 99).size() <
        creature_targets(state, them, 0, 99).size()) {
      state.queue.push_back(make_choice(
        me,
        "defeat",
        [](Game_State& game) { return creature_targets(game, -1, 0, 99); },
        [](Game_State& game, int target) { defeat_creature(game, target); }
      ));
    }
  }
};

struct Snail_Thrower : Card_Effects {
  // Arms a weak ally with Hunter and Poisonous.
  static int ally_keywords(const Game_State& state, int, int card) {
    return effective_power(state, card) <= 4 ? (HUNTER | POISONOUS) : 0;
  }
};

struct Strange_Barrel : Card_Effects {
  static void on_defeated(Game_State& state, int, int controller) {
    const int me   = controller;
    const int them = 1 - me;
    for (int i = 0; i < 2; ++i) {
      Player& victim = state.players[them];
      if (victim.hand.size() == 0) break;
      const int position = next_random(state, victim.hand.size());
      state.players[me].hand.push_back(victim.hand[position]);
      victim.hand.erase(victim.hand.begin() + position);
    }
  }
};

struct Tiger_Squirrel : Card_Effects {
  static void on_play(Game_State& state, int card) {
    const int me   = controller_of(state, card);
    const int them = 1 - me;
    state.queue.push_back(make_choice(
      me,
      "defeat",
      [them](Game_State& game) { return creature_targets(game, them, 7, 99); },
      [](Game_State& game, int target) { defeat_creature(game, target); }
    ));
  }
};

struct Turbo_Bug : Card_Effects {
  static void on_attack(Game_State& state, int card) {
    const int them = 1 - controller_of(state, card);
    if (state.players[them].life > 1) state.players[them].life = 1;
  }
};

struct Tusked_Extorter : Card_Effects {
  static void on_attack(Game_State& state, int card) {
    const int them = 1 - controller_of(state, card);
    state.queue.push_back(make_choice(
      them,
      "discard",
      [them](Game_State& game) { return cards_of(game.players[them].hand); },
      [them](Game_State& game, int card) {
        discard_from_hand(game, them, {card});
      }
    ));
  }
};

struct Urchin_Hurler : Card_Effects {
  static int ally_power_bonus(const Game_State&, int, bool its_turn) {
    return its_turn ? 2 : 0;
  }
};

// The design-to-struct mapping. A card with no ability has no row here and
// falls back to Card_Effects. This is the only place that lists every card;
// nothing else in the codebase needs to.
#define MINDBUG_CARD_LIST                               \
  X(AXOLOTL_HEALER, Axolotl_Healer)                     \
  X(BEE_BEAR, Bee_Bear)                                 \
  X(BRAIN_FLY, Brain_Fly)                               \
  X(CHAMELEON_SNIPER, Chameleon_Sniper)                 \
  X(COMPOST_DRAGON, Compost_Dragon)                     \
  X(DEATHWEAVER, Deathweaver)                           \
  X(ELEPHANTOPUS, Elephantopus)                         \
  X(EXPLOSIVE_TOAD, Explosive_Toad)                     \
  X(FERRET_BOMBER, Ferret_Bomber)                       \
  X(GIRAFFODILE, Giraffodile)                           \
  X(GOBLIN_WEREWOLF, Goblin_Werewolf)                   \
  X(GRAVE_ROBBER, Grave_Robber)                         \
  X(HARPY_MOTHER, Harpy_Mother)                         \
  X(KANGASAURUS_REX, Kangasaurus_Rex)                   \
  X(KILLER_BEE, Killer_Bee)                             \
  X(LONE_YETI, Lone_Yeti)                               \
  X(MYSTERIOUS_MERMAID, Mysterious_Mermaid)             \
  X(SHARK_DOG, Shark_Dog)                               \
  X(SHARKY_CRAB_DOG_MUMMYPUS, Sharky_Crab_Dog_Mummypus) \
  X(SHIELD_BUGS, Shield_Bugs)                           \
  X(SNAIL_HYDRA, Snail_Hydra)                           \
  X(SNAIL_THROWER, Snail_Thrower)                       \
  X(STRANGE_BARREL, Strange_Barrel)                     \
  X(TIGER_SQUIRREL, Tiger_Squirrel)                     \
  X(TURBO_BUG, Turbo_Bug)                               \
  X(TUSKED_EXTORTER, Tusked_Extorter)                   \
  X(URCHIN_HURLER, Urchin_Hurler)

// Calls visit(ability), where `ability` is the struct for `design` (an empty,
// stateless tag: the call it makes is picked at compile time per struct, the
// same as calling a plain function, with nothing built or freed at runtime).
// The switch below is the one and only place a design name chooses a type;
// every query in this file is a one-line call to dispatch().
template <class Visit>
static auto dispatch(int design, Visit&& visit) {
  switch (design) {
#define X(NAME, TYPE) \
  case NAME: return visit(TYPE());
    MINDBUG_CARD_LIST
#undef X
    default: return visit(Card_Effects());
  }
}

// ---- Queries dispatch() answers ----

void trigger_play(Game_State& state, int card) {
  dispatch(design_of(card), [&](auto ability) {
    ability.on_play(state, card);
  });
}

void trigger_attack(Game_State& state, int card) {
  dispatch(design_of(card), [&](auto ability) {
    ability.on_attack(state, card);
  });
}

void trigger_defeated(Game_State& state, int card, int controller) {
  dispatch(design_of(card), [&](auto ability) {
    ability.on_defeated(state, card, controller);
  });
}

int ally_power_bonus(const Game_State& state, int ally, bool its_turn) {
  return dispatch(design_of(ally), [&](auto ability) {
    return ability.ally_power_bonus(state, ally, its_turn);
  });
}

int self_power_bonus(const Game_State& state, int card) {
  return dispatch(design_of(card), [&](auto ability) {
    return ability.self_power_bonus(state, card);
  });
}

int ally_keywords(const Game_State& state, int ally, int card) {
  return dispatch(design_of(ally), [&](auto ability) {
    return ability.ally_keywords(state, ally, card);
  });
}

int self_keywords(const Game_State& state, int card) {
  return dispatch(design_of(card), [&](auto ability) {
    return ability.self_keywords(state, card);
  });
}

int mirrored_keywords(const Game_State& state, int card) {
  return dispatch(design_of(card), [&](auto ability) {
    return ability.mirrored_keywords(state, card);
  });
}

bool block_prevented(const Game_State& state, int attacker, int blocker) {
  const bool self_prevented = dispatch(design_of(attacker), [&](auto ability) {
    return ability.self_block_prevented(state, attacker, blocker);
  });
  if (self_prevented) return true;

  for (int ally : state.players[controller_of(state, attacker)].creatures) {
    const bool ally_prevented = dispatch(design_of(ally), [&](auto ability) {
      return ability.ally_block_prevented(state, ally, attacker, blocker);
    });
    if (ally_prevented) return true;
  }
  return false;
}

bool play_ability_suppressed(const Game_State& state, int controller) {
  for (int enemy : state.players[1 - controller].creatures) {
    const bool suppressed = dispatch(design_of(enemy), [](auto ability) {
      return ability.suppresses_enemy_play_ability();
    });
    if (suppressed) return true;
  }
  return false;
}

}  // namespace mindbug
