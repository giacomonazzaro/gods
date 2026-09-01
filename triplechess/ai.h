#pragma once

#include "models.h"

namespace triplechess {

// Value of `state` from `player`'s perspective. Terminal: +1 win, -1 loss, 0
// draw. Otherwise a piece-count-plus-advancement heuristic squashed into
// (-1, 1): winning is reaching the opponent's home row, so a piece further
// along that path is worth more.
float evaluate_state(const Game_State& state, int player);

}  // namespace triplechess
