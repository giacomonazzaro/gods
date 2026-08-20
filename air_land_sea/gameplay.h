#pragma once

#include <air_land_sea/models.h>

#include <algorithm>
#include <functional>
#include <random>
#include <vector>

namespace air_land_sea {

// A list of options a choice offers. Held inline: a search builds these on
// every node it looks at.
using Targets = Array_Inline<int, 16>;

// ---- Turn moves ----
//
// A turn move is carried as one int: which card to play, which column to play
// it in, and whether it goes face down. WITHDRAW_MOVE is the one move that is
// not about a card.

constexpr int WITHDRAW_MOVE = 255;

inline int pack_move(int card, int position, bool face_down) {
  return card * 8 + position * 2 + (face_down ? 1 : 0);
}
inline int  move_card(int move) { return move / 8; }
inline int  move_position(int move) { return move / 2 % 4; }
inline bool move_face_down(int move) { return move % 2 == 1; }

// Transport moves a card to another column, so its option carries both.
inline int  pack_transport(int card, int position) { return card * 4 + position; }
inline int  transport_card(int option) { return option / 4; }
inline int  transport_position(int option) { return option % 4; }

// The option that declines an ability whose text says "may".
constexpr int DECLINE = -1;

// ---- Queries ----

// Strength this card counts for right now: its printed number face up, 2 face
// down, and 4 when Escalation or Cover Fire raises it.
int strength_in_play(const Game_State& state, const Placement& placement);

// Everything one player has in one column, Support from the theaters next to
// it included.
int side_strength(const Game_State& state, int position, int player);

// True when that player has the higher strength in the column. The first
// player wins ties, which also covers a column no one has played in.
bool controls_theater(const Game_State& state, int position, int player);

int theaters_controlled(const Game_State& state, int player);

// The moves the player whose turn it is may take. The pending choice offers
// these in order, so an option index means the same thing here and in the UI.
Targets turn_moves(const Game_State& state);

// Victory points a player has. Feeds the game-over score line.
int compute_player_score(const Game_State& state, int player);

// ---- Mechanics ----

// Put a card on the table for `player`. Containment and Blockade may destroy
// it on the way in; otherwise a face-up card's ability happens.
void play_card(
  Game_State& state, int card, int position, bool face_down, int player
);

// Turn a card that is face up face down, or the other way round. A card turned
// face up uses its ability.
void flip_card(Game_State& state, int card);

// Take a card off the table and put it face down at the bottom of the deck.
void destroy_card(Game_State& state, int card);

// Deal a new battle: shuffle all 18 cards, 6 to each player, rotate the
// theaters and hand the first-player card to the other player.
void deal_battle(Game_State& state);

// ---- Choice helpers ----
//
// get_targets runs again when the choice resolves, so an option index always
// means the same target.

Choice make_choice(
  int                                   player,
  const char*                           description,
  std::function<Targets(Game_State&)>   get_targets,
  std::function<void(Game_State&, int)> on_chosen
);

// Rates the position for `player`. A win beats every unfinished position and a
// loss loses to every unfinished position. Victory points are what the game is
// about; the theaters held right now break the ties. (inline: the search
// templates need to see it, without a duplicate definition across translation
// units.)
inline float evaluate_state(const Game_State& state, int player) {
  if (state.game_over) return state.winner == player ? 2.0f : 0.0f;

  const int opponent   = 1 - player;
  const float points   = (float)state.points[player] -
                       (float)state.points[opponent];
  const float theaters = (float)theaters_controlled(state, player) - 1.5f;

  const float score = 1.0f + points / (float)(2 * POINTS_TO_WIN) +
                      theaters / 12.0f;
  return std::min(std::max(score, 0.01f), 1.99f);
}

// One position `player` cannot tell apart from `state`.
//
// A player has seen their own hand, every face-up card on the table, and their
// own face-down cards. The opponent's hand, the deck and the opponent's
// face-down cards are one pool of unknowns. So take the 18 cards, drop what has
// been seen, shuffle the rest, and fill the hidden places again out of it. The
// places keep their sizes; only which card is in them changes.
inline Game_State sample_state(
  const Game_State& concrete, int player, std::mt19937& rng
) {
  auto sampled = Game_State(concrete);

  auto is_seen = std::array<bool, CARD_COUNT>{};
  for (int card : sampled.hands[player]) is_seen[card] = true;
  for (const Placement& placement : sampled.board) {
    if (!placement.face_down || placement.owner == player) {
      is_seen[placement.card] = true;
    }
  }

  auto unseen = std::vector<uint8_t>();
  for (int card = 0; card < CARD_COUNT; ++card) {
    if (!is_seen[card]) unseen.push_back((uint8_t)card);
  }
  std::shuffle(unseen.begin(), unseen.end(), rng);

  int next = 0;
  for (int i = 0; i < sampled.hands[1 - player].size(); ++i) {
    sampled.hands[1 - player][i] = unseen[next++];
  }
  for (int i = 0; i < sampled.deck.size(); ++i) {
    sampled.deck[i] = unseen[next++];
  }
  for (Placement& placement : sampled.board) {
    if (placement.face_down && placement.owner != player) {
      placement.card = unseen[next++];
    }
  }
  return sampled;
}

}  // namespace air_land_sea
