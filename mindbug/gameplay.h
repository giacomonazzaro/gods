#pragma once

#include <mindbug/models.h>

#include <algorithm>
#include <functional>
#include <random>
#include <string>
#include <vector>

namespace mindbug {

// Fill card_designs from a cards.json file. Must be called once before any
// game is set up. Returns false if the file is missing or malformed.
bool load_card_designs(const std::string& path = "mindbug/cards.json");

// Deal a game: shuffle the 48-card deck, give each player 5 cards in hand and
// 5 face down, and ask for the first decision.
Game_State quick_setup(int seed);


// A list of cards a choice offers, or of moves a player has. Held inline: the
// search builds these on every node it looks at.
using Targets    = Array_Inline<int, 8>;
using Turn_Moves = Array_Inline<Turn_Action, 8>;

// Power of a creature in play, after the auras and self conditions that change
// it.
int effective_power(const Game_State& state, int card);

// Keywords the creature has right now, printed ones plus granted ones.
int effective_keywords(const Game_State& state, int card);

// Keywords from what's printed and from this side granting them, not from
// copying the enemy's. Sharky uses this to see what the enemy has without
// seeing its own copy of it.
int own_keywords(const Game_State& state, int card);

// True if `blocker` is allowed to block `attacker`. `attacker_keywords` is
// passed in because a loop over the creatures that could block works it out
// once, and it is the same for every one of them.
bool can_block(
  const Game_State& state,
  int               attacker,
  int               attacker_keywords,
  int               blocker
);

// Take `card` out of one of a player's card lists. It is always in the list:
// the callers read the card out of the list itself.
template <class T, int N>
void remove_card(Array_Inline<T, N>& cards, int card) {
  for (int i = 0; i < cards.size(); ++i) {
    if (cards[i] != card) continue;
    cards.erase(cards.begin() + i);
    return;
  }
}

// The actions the active player may take. The pending choice offers these in
// order, so an action index means the same thing here and in the UI.
Turn_Moves turn_actions(const Game_State& state);

// Take a creature out of play: exhaust it instead if Tough has not been used
// yet, otherwise put it in its controller's discard pile and trigger its
// Defeated ability.
void defeat_creature(Game_State& state, int card);

// 1 for the winner, 0 otherwise. Feeds the game-over score line.
int compute_player_score(const Game_State& state, int player);

// ---- Mechanics the card effects are written with ----

// Put a card into play as a creature under `controller` and trigger its Play
// ability.
void enter_play(Game_State& state, int card, int controller);

// Move a creature already in play to the other player.
void take_control(Game_State& state, int card, int controller);

void lose_life(Game_State& state, int player, int amount);

// Creatures a player has in play (-1 for either player) whose power is between
// min_power and max_power.
Targets creature_targets(
  const Game_State& state, int controller, int min_power, int max_power
);

// ---- Choice helpers ----
//
// get_targets runs again when the choice resolves, so an option index always
// means the same target. Every target is a card; `description` says which zone
// it is in.

Choice make_choice(
  int                                   player,
  const char*                           description,
  std::function<Targets(Game_State&)>   get_targets,
  std::function<void(Game_State&, int)> on_chosen
);

// Every selection of `count` targets (or of up to `count`, if up_to), in the
// order a multi-choice indexes them: option i picks combination i.
std::vector<std::vector<int>> target_combinations(
  const Targets& targets, int count, bool up_to
);

Choice make_multi_choice(
  int                                                       player,
  const char*                                               description,
  std::function<Targets(Game_State&)>                       get_targets,
  int                                                       count,
  bool                                                      up_to,
  std::function<void(Game_State&, const std::vector<int>&)> on_chosen
);

// The int a turn action is carried as in the pending choice: the card, with bit
// 8 set when the action is an attack.
inline int pack_turn_action(const Turn_Action& action) {
  return action.card | (action.is_attack ? 256 : 0);
}

inline Turn_Action unpack_turn_action(int packed) {
  return Turn_Action{(packed & 256) != 0, (uint8_t)(packed & 255)};
}

// Rates the position for `player`. A win beats every unfinished position and a
// loss loses to every unfinished position. Life is what the game is about;
// board power and cards left break the ties. (inline: the search templates need
// to see it, without a duplicate definition across translation units.)
inline float evaluate_state(const Game_State& state, int player) {
  const int opponent = 1 - player;
  if (state.game_over) return state.winner == player ? 2.0f : 0.0f;

  // float life     = state.players[player].life;
  // float life_opp = state.players[opponent].life;
  float mindbugs = std::min(
    (int)state.players[player].mindbugs, state.players[opponent].hand.size()
  );
  float mindbugs_opp = std::min(
    (int)state.players[opponent].mindbugs, state.players[player].hand.size()
  );

  float my_cards    = cards_left(state, player);
  float their_cards = cards_left(state, opponent);

  if (my_cards == 0 && state.current_player == player) return 0.0f;
  if (their_cards == 0 && state.current_player == opponent) return 2.0f;

  float score = my_cards + 2 * mindbugs;
  float den   = (my_cards + their_cards) + 2 * (mindbugs + mindbugs_opp);
  if (den > 0.0f)
    score /= den;
  else
    score = 0.5f;

  // Encourage search attacking.
  if (state.attacker != -1 && state.current_player == player) {
    score += 0.001f;
  }

  assert(score >= 0.0f && score <= 1.001f);
  return score;
}

// One position `player` cannot tell apart from `state`.
//
// A player has seen their own hand, both discard piles and everything in play.
// Every other card is the same unknown to them: the opponent's hand, both draw
// piles and the 28 cards the deal set aside are one pool, and a card in a
// hidden zone could be any card of the deck that has not been shown. So take
// the deck, drop what has been seen, shuffle the rest, and deal the hidden
// cards again out of it. The zones keep their sizes; only what the cards are
// changes.
inline Game_State sample_state(
  const Game_State& concrete, int player, std::mt19937& rng
) {
  auto sampled = Game_State(concrete);

  // Cards this player has seen: their own hand, both discard piles, and
  // everything in play or part of the attack being resolved.
  auto is_seen = std::vector<bool>(all_cards.size(), false);
  for (int card : sampled.players[player].hand) is_seen[card] = true;
  for (int side = 0; side < 2; ++side) {
    for (int card : sampled.players[side].discard) is_seen[card] = true;
    for (int card : sampled.players[side].creatures) is_seen[card] = true;
  }
  if (sampled.played_card >= 0) is_seen[sampled.played_card] = true;
  if (sampled.attacker >= 0) is_seen[sampled.attacker] = true;
  if (sampled.blocker >= 0) is_seen[sampled.blocker] = true;

  // Everything else is the same unknown, the 28 cards the deal set aside
  // included.
  auto unseen = std::vector<uint8_t>();
  for (int card = 0; card < (int)all_cards.size(); ++card) {
    if (!is_seen[card]) unseen.push_back((uint8_t)card);
  }
  std::shuffle(unseen.begin(), unseen.end(), rng);

  // Deal the hidden zones again out of the unseen cards. The zones keep
  // their sizes; only which cards are in them changes.
  int  next   = 0;
  auto refill = [&](auto& zone) {
    for (int i = 0; i < zone.size(); ++i) zone[i] = unseen[next++];
  };
  refill(sampled.players[player].draw_pile);
  refill(sampled.players[1 - player].hand);
  refill(sampled.players[1 - player].draw_pile);
  return sampled;
}

void draw_back_up_to_hand_size(Game_State& state);

}  // namespace mindbug
