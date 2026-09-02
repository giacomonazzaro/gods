#pragma once

#include <string>

#include <chess/models.h>
#include <game/agent.h>
#include <giocamo/play.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>

// UI agent for chess: drag a piece onto a square it can legally move to (or
// onto the piece standing there, for a capture) to make that move.
// gesture_map (rebuilt from legal_moves each turn) and process_gestures,
// both from giocamo/play.h, do the picking up, highlighting, and dropping —
// the same as every other game built on giocamo. Promotions auto-queen.
struct Chess_Agent_UI : Agent_UI {
  void message(const std::string&) override {}
  int  choose_action(Game& game, const Choice& choice) override;
};
