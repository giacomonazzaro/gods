#pragma once

#include <basic/array_inline.h>
#include <game/game.h>
#include <struct/print.h>

#include <array>
#include <cstdint>

namespace no_thanks {

// No Thanks! by Thorsten Gimmler, for three players.
//
// The deck holds the cards 3 to 35. Nine of them are taken out without anyone
// seeing them, so 24 are played. One card lies face up. The player to move
// either takes it, with every chip lying on it, or pays one chip to pass it to
// the next player. A player with no chips must take the card. Whoever takes a
// card turns the next one over and decides again. The game ends when the last
// card is taken. A card counts its number, except that in a run of consecutive
// cards only the lowest one counts, and every chip left counts -1. The lowest
// score wins.

constexpr int PLAYER_COUNT   = 3;
constexpr int LOWEST_CARD    = 3;
constexpr int HIGHEST_CARD   = 35;
constexpr int CARD_COUNT     = HIGHEST_CARD - LOWEST_CARD + 1;  // 33.
constexpr int DECK_SIZE      = 24;
constexpr int STARTING_CHIPS = 11;

// The option indices of the pending choice. The card can always be taken; the
// chip can only be paid by a player who still has one, and then it is offered
// second.
constexpr int TAKE_CARD = 0;
constexpr int PAY_CHIP  = 1;

struct Game_State : Game {
  // Cards are their own numbers, 3 to 35, so they fit in a byte. A state is
  // copied at every node a search looks at, which is why the lists are inline.
  //
  // The deck is face down, the card turned over next is the last one.
  Array_Inline<uint8_t, DECK_SIZE>                    deck;
  std::array<Array_Inline<uint8_t, DECK_SIZE>, PLAYER_COUNT> taken;

  std::array<uint8_t, PLAYER_COUNT> chips;
  // The card lying face up, or 0 once the last one has been taken.
  uint8_t card_on_table = 0;
  // Chips lying on that card, paid by the players who passed it on.
  uint8_t chips_on_card = 0;

  uint8_t current_player = 0;
  bool    game_over      = false;

  Game_State() { chips.fill(STARTING_CHIPS); }

  bool   is_game_over() const override { return game_over; }
  Choice next_choice() override;
  void   init(int seed = 0) override;
};

}  // namespace no_thanks

// visit_struct opens its own namespace, so this belongs at global scope.
VISITABLE_STRUCT(
  no_thanks::Game_State,
  deck,
  taken,
  chips,
  card_on_table,
  chips_on_card,
  current_player,
  game_over
);
