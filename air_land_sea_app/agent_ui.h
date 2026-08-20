#pragma once

#include <air_land_sea/models.h>
#include <game/agent.h>
#include <giocamo/play.h>

// The player as an Agent: highlights what the pending choice can take, waits
// for a card or a theater to be clicked (or for a button, where the choice is
// not about either), and answers with the matching action index.
struct Air_Land_Sea_Agent_UI : Agent_UI {
  int  local_seat = 0;
  bool hot_seat   = false;

  // A turn takes three picks: which card, face up or face down, and which
  // theater. These hold the picks made so far. -1 means "not picked yet".
  int picked_card = -1;
  int picked_mode = -1;  // 0 = face up, 1 = face down.
  // Transport picks a card first and a theater second.
  int picked_transport = -1;

  void message(const std::string&) override {}
  void reset() override;

  int choose_action(Game& game, const Choice& choice) override;
};
