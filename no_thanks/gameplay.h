#pragma once

#include <algorithm>
#include <array>
#include <climits>
#include <random>
#include <vector>

#include "models.h"

namespace no_thanks {

// The cards `player` has taken, plus the chips they still hold. Only the lowest
// card of a run of consecutive cards counts, and every chip counts -1. Lower is
// better, and a score can be negative.
int player_score(const Game_State& state, int player);

// The player with the lowest score. On a tie the lowest seat number of the
// tied players is returned.
int winning_player(const Game_State& state);

// Turns the next card of the deck over, or ends the game when the deck is
// empty. The player who took the last card stays the player to move.
void reveal_next_card(Game_State& state);

// Puts the card on the table, and the chips lying on it, in front of the player
// to move, then turns the next card over.
void take_card(Game_State& state);

// Pays one chip onto the card and passes it to the next player.
void pay_chip(Game_State& state);

// A deal, ready to play.
Game_State quick_setup(int seed);

// Rates the position for `player`. Higher is better, so it is the other way
// around from the score. A won position rates above every unfinished one and a
// lost position below every unfinished one, which is what the searches need.
// (inline: the search templates need to see it, without a duplicate definition
// across translation units.)
inline float evaluate_state(const Game_State& state, int player) {
  int own = player_score(state, player);
  own -= state.chips[player] * 0.1;
  float best_other = INT32_MAX;
  for (int other = 0; other < PLAYER_COUNT; ++other) {
    if (other == player) continue;
    best_other = std::min(
      best_other, player_score(state, other) - state.chips[other] * 0.1f
    );
  }
  if (state.game_over) return own <= best_other ? 2.0f : 0.0f;

  // A low score is what a player wants, so the lead is how far the best other
  // score sits above this player's own: it is positive when this player is
  // winning. The chips still held are already part of the score, so paying a
  // chip costs a point and taking a card with chips on it gains some. Dividing
  // by the largest card keeps a realistic lead inside the 0.01 to 1.99 range.
  float lead = (float)(best_other - own) / (float)HIGHEST_CARD;
  return std::min(std::max(1.0f + lead, 0.01f), 1.99f);
}

// One deal `player` cannot tell apart from `state`. Every card that nobody has
// taken and that is not lying face up is unseen: the nine cards out of the game
// and the deck are one pool. Shuffle it and fill the deck again; it keeps its
// size, only which cards are in it changes.
inline Game_State sample_state(
  const Game_State& concrete, int player, std::mt19937& rng
) {
  auto sampled = Game_State(concrete);

  auto is_seen = std::array<bool, HIGHEST_CARD + 1>{};
  for (int other = 0; other < PLAYER_COUNT; ++other) {
    for (uint8_t card : sampled.taken[other]) is_seen[card] = true;
  }
  if (sampled.card_on_table != 0) is_seen[sampled.card_on_table] = true;

  auto unseen = std::vector<uint8_t>();
  for (int card = LOWEST_CARD; card <= HIGHEST_CARD; ++card) {
    if (!is_seen[card]) unseen.push_back((uint8_t)card);
  }
  std::shuffle(unseen.begin(), unseen.end(), rng);

  for (int i = 0; i < sampled.deck.size(); ++i) sampled.deck[i] = unseen[i];
  return sampled;
}

}  // namespace no_thanks
