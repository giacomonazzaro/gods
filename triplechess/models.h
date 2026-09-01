#pragma once

#include <game/game.h>

#include <array>
#include <struct/visit.hpp>

namespace triplechess {

constexpr int BOARD_SIZE = 8;

// Piece type stored in a board slot, ignoring player. A slot holds 0 when
// empty, a positive value for player 0's piece, and the negative of the same
// value for player 1's piece. So board values run -3..3, and the magnitude is
// the Piece type.
enum Piece { EMPTY = 0, ROCK = 1, PAPER = 2, SCISSORS = 3 };

// Player owning a board value: 0 (value > 0), 1 (value < 0), -1 empty.
inline int piece_color(int value) {
  if (value > 0) return 0;
  if (value < 0) return 1;
  return -1;
}

// Type (ROCK/PAPER/SCISSORS) of a board value, regardless of player.
inline int piece_type(int value) { return value < 0 ? -value : value; }

// Board value for a piece of `type` owned by `player` (0 or 1).
inline int make_piece(int type, int player) {
  return player == 0 ? type : -type;
}

// True when a piece of `attacker_type` beats a piece of `defender_type`:
// rock beats scissors, scissors beats paper, paper beats rock.
inline bool beats(int attacker_type, int defender_type) {
  return (attacker_type == ROCK && defender_type == SCISSORS) ||
         (attacker_type == SCISSORS && defender_type == PAPER) ||
         (attacker_type == PAPER && defender_type == ROCK);
}

// board[row][col]; row 0 is player 0's home row, row BOARD_SIZE-1 is player
// 1's. One byte per cell, so the whole board is trivially copyable — cheap to
// copy on its own during move generation, separate from the rest of the game
// state.
using Board = std::array<std::array<signed char, BOARD_SIZE>, BOARD_SIZE>;

struct Game_State : Game {
  Board board;

  int current_player = 0;   // 0 or 1.
  int winner         = -1;  // -1 none yet, 0/1 the winner, 2 a draw.

  bool game_over = false;

  Game_State() {
    for (auto& row : board) row.fill(EMPTY);
  }

  bool   is_game_over() const override { return game_over; }
  Choice next_choice() override;
  void   init(int seed = 0) override;

  void switch_turn() { current_player = 1 - current_player; }
};

}  // namespace triplechess

VISITABLE_STRUCT(
  triplechess::Game_State, board, current_player, winner, game_over
);
