#pragma once

#include <basic/array_inline.h>
#include <game/game.h>
#include <struct/print.h>

#include <array>
#include <cstdint>
#include <vector>

namespace air_land_sea {

// Air, Land, & Sea by Jon Perry. Two players fight a series of battles over
// three theaters. Winning a battle scores victory points; the first player to
// 12 points wins the game.

constexpr int CARD_COUNT     = 18;
constexpr int THEATER_COUNT  = 3;
constexpr int HAND_SIZE      = 6;
constexpr int POINTS_TO_WIN  = 12;
constexpr int FACE_DOWN_STRENGTH = 2;
// Escalation makes your face-down cards this strong, and Cover Fire makes the
// cards it covers this strong.
constexpr int BOOSTED_STRENGTH = 4;

enum Theater : uint8_t {
  AIR,
  LAND,
  SEA,
};

enum Ability : uint8_t {
  NO_ABILITY,
  // Ongoing: in effect for as long as the card is face up.
  SUPPORT,
  AERODROME,
  CONTAINMENT,
  COVER_FIRE,
  ESCALATION,
  BLOCKADE,
  // Instant: happens once, when the card is played face up or flipped face up.
  AIR_DROP,
  MANEUVER,
  REINFORCE,
  AMBUSH,
  DISRUPT,
  TRANSPORT,
  REDEPLOY,
};

// The printed card. The 18 cards never change, so this lives outside
// Game_State: copying a state (as a search does per node) must not copy them.
// A card is named by its index, which is theater * 6 + strength - 1.
struct Card_Design {
  const char* name;
  const char* text;
  Ability     ability;
};

extern const Card_Design card_designs[CARD_COUNT];

inline int     card_theater(int card) { return card / 6; }
inline int     card_strength(int card) { return card % 6 + 1; }
inline Ability ability_of(int card) { return card_designs[card].ability; }

// An instant ability happens once; an ongoing one lasts while the card is face
// up.
inline bool is_instant(Ability ability) { return ability >= AIR_DROP; }

// One card on the table. The order in Game_State::board is the order the cards
// were placed in, so a card later in the list covers the earlier cards of the
// same column and owner.
struct Placement {
  uint8_t card      = 0;  // Index of the card, 0..17.
  uint8_t position  = 0;  // Which of the three columns it sits in, 0..2.
  uint8_t owner     = 0;
  uint8_t face_down = 0;
};

struct Game_State : Game {
  // Every card index fits in a byte, and a state is copied at every node a
  // search looks at, so the byte-wide types keep those copies small.
  //
  // Capacities are what a list holds at its fullest, not what it usually
  // holds: past it an Array_Inline goes to the heap. A hand starts at 6 and
  // Redeploy puts a card back into it. The board holds the 12 cards dealt plus
  // the one Reinforce can add.
  std::array<Array_Inline<uint8_t, 8>, 2> hands;
  Array_Inline<uint8_t, 8>                deck;  // Not dealt, top card first.
  Array_Inline<Placement, 16>             board;

  // Which theater sits in each column. The columns are shuffled at setup and
  // rotated after every battle, and two columns next to each other are
  // adjacent, so this is what the adjacency rules read.
  std::array<uint8_t, THEATER_COUNT> theaters = {AIR, LAND, SEA};

  std::array<uint8_t, 2> points = {0, 0};
  // Air Drop lets that player deploy to a non-matching theater on their next
  // turn. Set when Air Drop is played, cleared by the next card they play.
  std::array<uint8_t, 2> air_drop = {0, 0};

  uint8_t first_player   = 0;  // Wins ties for control of a theater.
  uint8_t current_player = 0;
  // The player who conceded the battle, or -1 while the battle is on.
  int8_t withdrew = -1;
  // The turn's action is done; the turn passes once the abilities it started
  // have been resolved.
  bool turn_taken = false;
  // Redeploy gives the player another turn, so the turn does not pass.
  bool extra_turn = false;

  bool   game_over = false;
  int8_t winner    = -1;

  // Effects that still owe a player a decision, oldest first.
  std::vector<Choice> queue;

  // Dealing the next battle needs randomness. Kept as a plain seed so copying
  // a state during search stays cheap.
  unsigned int random_seed = 1;

  bool   is_game_over() const override { return game_over; }
  Choice next_choice() override;
  void   init(int seed = 0) override;
};

// Two columns next to each other are adjacent theaters.
inline bool is_adjacent(int position, int other) {
  return position - other == 1 || other - position == 1;
}

// The card on the table, or null when it is in a hand or in the deck.
inline const Placement* find_placement(const Game_State& state, int card) {
  for (const Placement& placement : state.board) {
    if (placement.card == card) return &placement;
  }
  return nullptr;
}

inline Placement* find_placement(Game_State& state, int card) {
  for (Placement& placement : state.board) {
    if (placement.card == card) return &placement;
  }
  return nullptr;
}

// True when no card of the same owner and column was placed after this one.
inline bool is_uncovered(const Game_State& state, int card) {
  const Placement* placement = find_placement(state, card);
  if (!placement) return false;
  bool found = false;
  for (const Placement& other : state.board) {
    if (other.card == card) {
      found = true;
      continue;
    }
    if (!found) continue;
    if (other.owner == placement->owner && other.position == placement->position)
      return false;
  }
  return true;
}

// True when that player has a face-up card with this ability on the table.
// Every ongoing ability is only in effect while its card is face up.
inline bool has_face_up(const Game_State& state, int player, Ability ability) {
  for (const Placement& placement : state.board) {
    if (placement.owner != player || placement.face_down) continue;
    if (ability_of(placement.card) == ability) return true;
  }
  return false;
}

// Cards both players have in a column, which is what Blockade counts.
inline int cards_in_theater(const Game_State& state, int position) {
  int count = 0;
  for (const Placement& placement : state.board) {
    if (placement.position == position) count += 1;
  }
  return count;
}

}  // namespace air_land_sea

// visit_struct opens its own namespace, so these belong at global scope.
VISITABLE_STRUCT(air_land_sea::Placement, card, position, owner, face_down);

VISITABLE_STRUCT(
  air_land_sea::Game_State,
  hands,
  deck,
  board,
  theaters,
  points,
  air_drop,
  first_player,
  current_player,
  withdrew,
  turn_taken,
  extra_turn,
  game_over,
  winner,
  random_seed
);
