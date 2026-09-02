#include "ui.h"

#include <tabletop/rendering.h>
#include <triplechess/gameplay.h>

#include <string>

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

std::vector<Thing> make_triplechess_squares() {
  std::vector<Thing> squares;
  const float        cell   = (float)SCAMORRA_CELL;
  const float        center = ((float)triplechess::BOARD_SIZE - 1.0f) / 2.0f;
  // Squares live in root-local coords; the root is centered on the screen, so
  // the board is centered around the origin. Row 0 (player 0's home row) sits
  // at the bottom of the screen.
  for (int row = 0; row < triplechess::BOARD_SIZE; ++row) {
    for (int col = 0; col < triplechess::BOARD_SIZE; ++col) {
      Thing square;
      square.name  = "sq" + std::to_string(row * triplechess::BOARD_SIZE + col);
      square.shape = rectangle_shape({cell, cell});
      square.transform.x = ((float)col - center) * cell;
      square.transform.y = (center - (float)row) * cell;
      bool dark          = (row + col) % 2 == 0;
      square.color       = dark ? Color{150, 110, 70, 255}
                                : Color{235, 210, 170, 255};
      square.locked      = true;
      square.capacity    = 1;  // Holds at most one piece.
      squares.push_back(square);
    }
  }
  return squares;
}

Shape triplechess_piece_shape(int type) {
  switch (type) {
    case triplechess::ROCK: return Shape_Circle{32.0f};
    case triplechess::SCISSORS: return Shape_Triangle{40.0f};
    default: return Shape_Rectangle{{58.0f, 58.0f}, 8.0f};  // PAPER.
  }
}

Color triplechess_piece_color(int value) {
  if (triplechess::piece_color(value) == 0)
    return Color{215, 95, 60, 255};  // Player 0: terracotta.
  return Color{70, 120, 195, 255};   // Player 1: blue.
}

void draw_triplechess_hud(const triplechess::Game_State& state) {
  std::string label;
  Color       color = Color{230, 230, 230, 255};
  if (state.game_over) {
    if (state.winner == 2) {
      label = "Draw";
    } else {
      label = std::string(state.winner == 0 ? "Player 1" : "Player 2") +
              " wins!";
    }
  } else {
    label = std::string(state.current_player == 0 ? "Player 1" : "Player 2") +
            " to move";
  }
  render_text(label, 30.0f, 24.0f, 28, color);
}
