#include "ai.h"

#include <cmath>

namespace triplechess {

// How far a piece has advanced toward the row it needs to reach to win: 0 on
// its own home row, BOARD_SIZE - 1 on the opponent's.
static int advancement(int row, int player) {
  return player == 0 ? row : (BOARD_SIZE - 1 - row);
}

float evaluate_state(const Game_State& state, int player) {
  // Terminal positions dominate any heuristic estimate below.
  if (state.winner == player) return 1.0f;
  if (state.winner == 1 - player) return -1.0f;
  if (state.winner == 2) return 0.0f;  // Draw.

  float raw = 0.0f;
  for (int row = 0; row < BOARD_SIZE; ++row) {
    for (int col = 0; col < BOARD_SIZE; ++col) {
      int value = state.board[row][col];
      if (value == EMPTY) continue;
      int   owner = piece_color(value);
      float worth = 1.0f + (float)advancement(row, owner) * 0.15f;
      raw += owner == player ? worth : -worth;
    }
  }

  // Squash into (-1, 1): the heuristic asymptotes but never reaches a true
  // win/loss, so the search always prefers an actual win.
  return std::tanh(raw * 0.2f);
}

}  // namespace triplechess
