#pragma once

#include <mindbug/models.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>

#include <functional>
#include <string>
#include <vector>

// Face decoration for one card: the power it has right now while it is in play
// (auras change it), and a mark when it is exhausted. The cards the pending
// choice can take are outlined by the agent with highlight_thing_border.
std::function<void(const Table_State&, const Input&, bool)>
make_card_draw_callback(const mindbug::Game_State& state, int card);

// Whose turn it is. `local_seat` is "You".
void draw_mindbug_hud(const mindbug::Game_State& state, int local_seat);
