#pragma once

#include <game/game.h>

#include "models.h"

namespace triplechess {

// A single move. `from` and `to` are squares (row*BOARD_SIZE + col).
struct Move {
  int from;
  int to;
};

// Move lists stay inline (no heap allocation): a piece has at most 8
// destinations and there are at most 12 pieces on the board, so 128 is a
// generous ceiling, and legal_moves runs on every simulated ply during search.
using Move_List = Array_Inline<Move, 128>;

// All legal moves for the player to move. Each piece moves one square in any
// of the 8 directions, like a chess king:
//   - onto an empty square: a normal move.
//   - onto an enemy piece it beats (rock beats scissors, scissors beats
//     paper, paper beats rock): a capture.
//   - onto an enemy piece of the same type: a push. The pushed piece hops one
//     further square along the same direction, or is killed if that square
//     is off the board. Legal unless that square is on the board and
//     occupied.
//   - onto an enemy piece that beats it, or onto its own piece: not legal.
Move_List legal_moves(const Game_State& state);

// Apply `move` (assumed legal): move the piece, pushing an enemy piece of the
// same type one square further along (killing it if that square is off the
// board) if that is what the move does, then end the game if the mover
// reached the opponent's home row, or pass the turn.
void apply_move(Game_State& state, const Move& move);

// 1 if `player` has won, else 0. Feeds the game-over score line.
int compute_player_score(const Game_State& state, int player);

// Starting position, pieces R P S R P S centered on each player's home row,
// player 0 to move. The seed is unused (triplechess has no randomness); it
// matches the other games' setup signature.
Game_State quick_setup(int seed = 0);

}  // namespace triplechess
