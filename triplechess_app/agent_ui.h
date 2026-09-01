#pragma once

#include <game/agent.h>
#include <giocamo/play.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>
#include <triplechess/models.h>

#include <string>

// UI agent for triplechess: press down on a piece with a legal move to pick it
// up, drag it, and release over a destination square to move it there.
// Releasing anywhere else puts it back.
struct Triplechess_Agent_UI : Agent_UI {
  int selected_square = -1;  // Square being dragged from, or -1.

  void message(const std::string&) override {}
  int  choose_action(Game& game, const Choice& choice) override;
};
