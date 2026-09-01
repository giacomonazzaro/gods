#pragma once

#include <tabletop/tabletop.h>
#include <triplechess/models.h>

#include <vector>

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

// Square pitch in pixels; the board is BOARD_SIZE squares wide.
constexpr int SCAMORRA_CELL = 90;

// Build the BOARD_SIZE*BOARD_SIZE square Things: a centered grid of
// alternating light/dark squares. Square `row*BOARD_SIZE + col` ends up at
// thing-id `row*BOARD_SIZE + col` (the squares are appended first), so a
// square's id equals its board index.
std::vector<Thing> make_triplechess_squares();

// Shape for a piece type: rock is a circle, paper a square, scissors a
// triangle. Same shape for both players — color tells them apart.
Shape triplechess_piece_shape(int type);

// Fill color for a board value: warm for player 0, cool for player 1.
Color triplechess_piece_color(int value);

// HUD: whose turn it is, or the winner once the game ends.
void draw_triplechess_hud(const triplechess::Game_State& state);

// The piece Thing-id standing on `square` (see main.cpp), or -1 if the
// square is empty. Pieces are not children of squares (they are root
// children, repositioned directly, so the renderer can slide them between
// squares instead of snapping), so this is how other code finds which piece
// Thing sits on a given square.
int triplechess_piece_thing_on_square(int square);
