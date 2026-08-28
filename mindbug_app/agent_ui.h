#pragma once

#include <game/agent.h>
#include <giocamo/play.h>
#include <mindbug/models.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>

// The player as an Agent: highlights the cards the pending choice can take,
// waits for one to be clicked (or for a button, where the choice isn't about a
// card), and answers with the matching action index.
struct Mindbug_Agent_UI : Agent_UI {
  void message(const std::string&) override {}

  int choose_action(Game& game, const Choice& choice) override;
  int choose_action_internal(Game& game, const Choice& choice);
};
