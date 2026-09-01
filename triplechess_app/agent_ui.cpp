#include "agent_ui.h"

#include <triplechess/gameplay.h>

#include "ui.h"

int Triplechess_Agent_UI::choose_action(Game& game, const Choice&) {
  auto&                  state = static_cast<triplechess::Game_State&>(game);
  triplechess::Move_List moves = triplechess::legal_moves(state);

  // Which square (thing-id == board index) is under the cursor this frame,
  // if any. Tested against the square Things directly, not the topmost thing
  // under the cursor, so a piece drawn on top of a square does not shadow it.
  int square_count   = triplechess::BOARD_SIZE * triplechess::BOARD_SIZE;
  int hovered_square = -1;
  for (int square = 0; square < square_count; ++square) {
    if (point_in_thing(
          (float)input->mouse_x, (float)input->mouse_y, square, table
        )) {
      hovered_square = square;
      break;
    }
  }

  // Not dragging: pressing down on a piece with a legal move picks it up.
  if (selected_square < 0) {
    if (input->left_pressed && hovered_square >= 0) {
      for (const triplechess::Move& move : moves) {
        if (move.from == hovered_square) {
          selected_square = hovered_square;
          break;
        }
      }
    }
    return -1;
  }

  // Dragging: the picked-up piece follows the cursor. Its origin square and
  // the squares it can legally reach are highlighted by the HUD draw_callback
  // in main.cpp, which reads selected_square directly.
  int dragged_piece = triplechess_piece_thing_on_square(selected_square);
  if (dragged_piece >= 0) {
    table.world_transforms_animated[dragged_piece].x = (float)input->mouse_x;
    table.world_transforms_animated[dragged_piece].y = (float)input->mouse_y;
  }

  if (!input->left_released) return -1;

  // Released: a legal move from the drag's origin square to the square under
  // the cursor resolves it. Releasing anywhere else puts the piece back —
  // returning -1 without moving it leaves world_transforms untouched, so the
  // next frame's animation eases it back to its origin square on its own.
  int result = -1;
  if (hovered_square >= 0) {
    for (int i = 0; i < (int)moves.size(); ++i) {
      if (moves[i].from == selected_square && moves[i].to == hovered_square) {
        result = i;
        break;
      }
    }
  }
  selected_square = -1;
  return result;
}
