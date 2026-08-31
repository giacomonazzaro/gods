#pragma once

#include <air_land_sea/models.h>
#include <game/agent.h>
#include <giocamo/play.h>

// The player as an Agent: highlights what the pending choice can take, waits
// for a card or a theater to be clicked (or for a button, where the choice is
// not about either), and answers with the matching action index.
struct Air_Land_Sea_Agent_UI : Agent_UI {
  // Buttons run up from the bottom-left corner, beside the player's hand —
  // the same rail the hand-written "turn"/"transport" buttons use below.
  Air_Land_Sea_Agent_UI() {
    button_anchor = place_on_screen(240, 46, "left", "bottom", 20);
  }

  int  local_seat = 0;
  bool hot_seat   = false;

  // Transport picks a card first and a theater second.
  int picked_transport = -1;

  void message(const std::string&) override {}
  void reset() override;

  int choose_action(Game& game, const Choice& choice) override;
  int choose_action_internal(Game& game, const Choice& choice);
};
