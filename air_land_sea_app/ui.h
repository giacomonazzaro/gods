#pragma once

#include <air_land_sea/models.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>

#include <functional>
#include <string>

// The cards have no art: a card is a solid rectangle in the color of its
// theater, with its strength, its ability name and its ability text drawn on
// it.
Color       theater_color(int theater);
const char* theater_name(int theater);

// Face of one card: its strength, the strength it counts for right now while
// it is on the table, its ability, and the border of a card the pending choice
// can take.
//
// A card the local player is not allowed to see is drawn as a card back even
// when the table asks for its face, which is what stops SPACE-to-zoom from
// showing the opponent's face-down cards.
std::function<void(const Table_State&, const Input&, bool)>
make_card_draw_callback(
  const air_land_sea::Game_State& state,
  int                             card,
  int                             local_seat,
  bool                            hot_seat,
  bool                            highlighted = false
);

// Name of the theater sitting in this column, and the border of a column the
// pending choice can take.
std::function<void(const Table_State&, const Input&, bool)>
make_theater_draw_callback(
  const air_land_sea::Game_State& state, int position, bool highlighted = false
);

// Whose turn it is and how the battle stands. `local_seat` is "You".
void draw_air_land_sea_hud(
  const air_land_sea::Game_State& state, int local_seat
);
