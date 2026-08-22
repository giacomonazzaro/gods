#include <game/agent.h>
#include <game/game.h>
#include <game/mcts.h>
#include <game/minimax.h>
#include <giocamo/menu.h>
#include <giocamo/play.h>
#include <no_thanks/gameplay.h>
#include <no_thanks/models.h>
#include <struct/imgui.h>  // for draw_editor_ui()
#include <tabletop/config.h>
#include <tabletop/rendering.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

#include <algorithm>
#include <string>
#include <vector>

using namespace no_thanks;

// The card everyone is deciding about lies in the middle, with the chips paid
// for it beside it and the face-down deck on its right. The cards a player has
// taken lie in a row: the local player along the bottom edge, the other two
// along the top, left and right. Each row has the player's chips beside it.
static constexpr float ROW_SPREAD       = 56.0f;
static constexpr float BOTTOM_ROW_Y     = 330.0f;
static constexpr float BOTTOM_ROW_WIDTH = 1200.0f;
static constexpr float TOP_ROW_Y        = -330.0f;
static constexpr float TOP_ROW_X        = 400.0f;
static constexpr float TOP_ROW_WIDTH    = 640.0f;
static constexpr float DECK_X           = 260.0f;
static constexpr float POT_X            = -320.0f;
static constexpr float CHIP_SIZE        = 44.0f;
static constexpr float CHIP_SPREAD      = 20.0f;

// Every chip in the game is a thing of its own, so a pile is a fan of chips.
constexpr int CHIP_COUNT = PLAYER_COUNT * STARTING_CHIPS;
// A chip lies in a player's pile, or on the card: that pile is numbered
// PLAYER_COUNT.
constexpr int POT_PILE = PLAYER_COUNT;

// Where the debug snapshot of the game is written and read.
static const std::string SNAPSHOT_PATH = "data/debug_game_state.json";

// Thing ids. The 33 cards come first, and a card's id is its number minus the
// lowest one; the 33 chips follow.
static int card_thing(int card) { return card - LOWEST_CARD; }
static int thing_card(int thing) { return thing + LOWEST_CARD; }
static int chip_thing(int chip) { return CARD_COUNT + chip; }

static Rectangle centered(float x, float y, float width, float height) {
  return Rectangle{x - width / 2.0f, y - height / 2.0f, width, height};
}

static std::string cards_zone(int player) {
  return "p" + std::to_string(player) + "_cards";
}

static std::string chips_zone(int player) {
  return "p" + std::to_string(player) + "_chips";
}

// Which of the three places on the screen a player sits in: 0 is the bottom
// edge, where the local player is, 1 the top left and 2 the top right. Play
// passes from the bottom player to the top-left one and on to the top-right.
static int seat_on_screen(int player, int bottom_player) {
  return (player - bottom_player + PLAYER_COUNT) % PLAYER_COUNT;
}

// The row of taken cards and the chips pile of one seat.
static Rectangle row_rect(int seat) {
  const float card_height = (float)tt::CARD_HEIGHT;
  if (seat == 0)
    return centered(0.0f, BOTTOM_ROW_Y, BOTTOM_ROW_WIDTH, card_height);
  const float side = seat == 1 ? -1.0f : 1.0f;
  return centered(side * TOP_ROW_X, TOP_ROW_Y, TOP_ROW_WIDTH, card_height);
}

// A pile of chips is a fan, wide enough that all 33 chips still fit side by
// side without piling up on each other.
static Rectangle chips_rect(int seat) {
  // update_children_positions measures a child as a card, so the width that
  // keeps the fan at its full spread is counted with a card's width.
  const float width = (float)(CHIP_COUNT - 1) * CHIP_SPREAD +
                      (float)tt::CARD_WIDTH;
  // The local player's chips lie under their cards, to the right of the
  // buttons; the other two have theirs under their own row.
  if (seat == 0) return centered(220.0f, 468.0f, width, CHIP_SIZE);
  const float side = seat == 1 ? -1.0f : 1.0f;
  return centered(side * TOP_ROW_X, TOP_ROW_Y + 160.0f, width, CHIP_SIZE);
}

// Every place a thing can sit.
static std::vector<Thing> make_zones(int bottom_player) {
  const float card_width  = (float)tt::CARD_WIDTH;
  const float card_height = (float)tt::CARD_HEIGHT;

  auto zones = std::vector<Thing>();
  for (int player = 0; player < PLAYER_COUNT; ++player) {
    const int seat = seat_on_screen(player, bottom_player);
    zones.push_back(make_container_thing(
      row_rect(seat), ROW_SPREAD, 0.0f, true, cards_zone(player)
    ));
    zones.push_back(make_container_thing(
      chips_rect(seat), CHIP_SPREAD, 0.0f, true, chips_zone(player)
    ));
  }

  // The card being decided about, the chips paid for it, and the deck. The
  // chips on the card lie to its left, fanned the same way as a player's pile.
  zones.push_back(make_container_thing(
    centered(0.0f, 0.0f, card_width, card_height), 0.0f, 0.0f, true, "table"
  ));
  zones.push_back(make_container_thing(
    centered(POT_X, 0.0f, 380.0f, CHIP_SIZE), CHIP_SPREAD, 0.0f, true, "pot"
  ));
  zones.push_back(make_container_thing(
    centered(DECK_X, 0.0f, card_width, card_height), 0.0f, -3.0f, false, "deck"
  ));
  return zones;
}

// A card shows its number on its left edge: the cards of a row overlap, and
// the left edge is the part that stays visible.
static std::function<void(const Table_State&, const Input&, bool)>
make_card_draw_callback(int card) {
  return [card](const Table_State&, const Input&, bool face_up) {
    if (!face_up) return;
    const float width  = (float)tt::CARD_WIDTH;
    const float height = (float)tt::CARD_HEIGHT;
    render_text(
      std::to_string(card),
      -width / 2.0f + 12.0f,
      -height / 2.0f + 14.0f,
      42,
      Color{240, 240, 240, 255}
    );
  };
}

// The line above the buttons, and the state of each player.
static void draw_no_thanks_hud(const Game_State& state, int bottom_player) {
  const float x = 16.0f;
  render_text("No Thanks!", x, 16.0f, 26, Color{235, 235, 235, 255});

  std::string turn = state.game_over
                       ? "Game over"
                       : "Player " + std::to_string(state.current_player + 1) +
                           "'s turn";
  render_text(turn, x, 52.0f, 20, Color{255, 215, 0, 255});

  for (int player = 0; player < PLAYER_COUNT; ++player) {
    std::string line = "Player " + std::to_string(player + 1);
    if (player == bottom_player) line += " (you)";
    line += ":  score " + std::to_string(player_score(state, player)) +
            "   chips " + std::to_string(state.chips[player]);
    render_text(
      line, x, 84.0f + 26.0f * (float)player, 20, Color{210, 210, 210, 255}
    );
  }
}

// The local player's seat: two buttons, take the card or pay a chip.
struct No_Thanks_Agent_UI : Agent_UI {
  void message(const std::string&) override {}

  int choose_action(Game& game, const Choice& choice) override {
    Game_State&  state   = static_cast<Game_State&>(game);
    const Input& input   = *this->input;
    Choose       actions = choice.actions(game);
    const int    count   = action_options_count(actions);

    std::string take_label = "Take card " + std::to_string(state.card_on_table);
    if (state.chips_on_card > 0) {
      take_label += " and " + std::to_string(state.chips_on_card) + " chips";
    }

    Rectangle button = place_on_screen(300, 46, "left", "bottom", 20);
    if (immediate_button(button, take_label, input)) return TAKE_CARD;

    // The chip is only offered while the player has one; then it is the second
    // option the game lists.
    if (count > 1) {
      button.y -= button.height + 12.0f;
      if (immediate_button(button, "No Thanks! (pay a chip)", input)) {
        return PAY_CHIP;
      }
    }
    return -1;
  }
};

// No Thanks! on the table. The table is laid out once here; play_game deals the
// game and drives the loop through these hooks.
struct No_Thanks_Giocamo : Giocamo_With_History<Game_State> {
  No_Thanks_Giocamo(Game_State& game, No_Thanks_Agent_UI& agent_ui)
      : Giocamo_With_History<Game_State>(game, agent_ui) {}

  // The pile each chip lies in: a player, or POT_PILE for the card. The game
  // only counts chips, so this is what tells one chip from another.
  std::vector<int> chip_pile;

  Game_State&       nt_game() { return static_cast<Game_State&>(game); }
  const Game_State& nt_game() const {
    return static_cast<const Game_State&>(game);
  }

  // Moves chips from the piles that hold too many to the piles that hold too
  // few, until every pile holds what the game says. A chip that stays where it
  // is keeps its place in the fan, so only the chips that were paid or won
  // move on the screen.
  void move_chips_to_match_game() {
    const Game_State& state = this->nt_game();

    auto wanted = std::vector<int>(POT_PILE + 1, 0);
    for (int player = 0; player < PLAYER_COUNT; ++player) {
      wanted[player] = state.chips[player];
    }
    wanted[POT_PILE] = state.chips_on_card;

    auto held = std::vector<int>(POT_PILE + 1, 0);
    for (int pile : chip_pile) held[pile] += 1;

    for (int pile = 0; pile <= POT_PILE; ++pile) {
      while (held[pile] < wanted[pile]) {
        int from = -1;
        for (int other = 0; other <= POT_PILE; ++other) {
          if (held[other] > wanted[other]) from = other;
        }
        if (from == -1) break;  // Never: the 33 chips are always all somewhere.
        for (int chip = 0; chip < CHIP_COUNT; ++chip) {
          if (chip_pile[chip] != from) continue;
          chip_pile[chip] = pile;
          break;
        }
        held[from] -= 1;
        held[pile] += 1;
      }
    }
  }

  void init_table() override {
    table.is_drop_allowed = [](int, int, int) { return false; };

    // One Thing per card, in the order of the numbers, so a card's id is its
    // number minus the lowest one.
    for (int card = LOWEST_CARD; card <= HIGHEST_CARD; ++card) {
      auto thing  = make_card();
      thing.color = {55, 75, 105, 255};
      table.things.push_back(std::move(thing));
      table.draw_callbacks[card_thing(card)] = make_card_draw_callback(card);
    }

    // One Thing per chip. Each player starts with their own eleven.
    for (int chip = 0; chip < CHIP_COUNT; ++chip) {
      auto thing         = Thing();
      thing.shape        = circle_shape(CHIP_SIZE);
      thing.color        = {190, 160, 40, 255};
      thing.border_color = {120, 95, 20, 255};
      thing.border_width = 3.0f;
      thing.capacity     = 0;
      table.things.push_back(std::move(thing));
      chip_pile.push_back(chip / STARTING_CHIPS);
    }

    auto zone_ids = std::vector<int>();
    for (Thing& zone : make_zones(this->bottom_player)) {
      zone_ids.push_back(add_thing(table, std::move(zone)));
    }

    // Empty texture path: the table is drawn with root.color.
    auto root      = create_table_root(tt::WINDOW_WIDTH, tt::WINDOW_HEIGHT, "");
    root._children = zone_ids;
    root.color     = {0, 0, 0, 0};
    table.root     = add_thing(table, std::move(root));

    table.draw_callbacks[-1] = [this](const Table_State&, const Input&, bool) {
      draw_no_thanks_hud(this->nt_game(), this->bottom_player);
    };
  }

  void update_table_from_game() override {
    Game_State& state = this->nt_game();

    auto set_zone =
      [&](const std::string& name, const std::vector<int>& things) {
        const int zone               = find_thing(table, name);
        table.things[zone]._children = things;
        update_children_positions(zone, table, false);
      };

    for (int player = 0; player < PLAYER_COUNT; ++player) {
      // Sorted, so a run of consecutive cards lies next to each other and the
      // player can see what the cards are worth.
      auto cards = std::vector<int>(
        state.taken[player].begin(), state.taken[player].end()
      );
      std::sort(cards.begin(), cards.end());
      auto things = std::vector<int>();
      for (int card : cards) things.push_back(card_thing(card));
      set_zone(cards_zone(player), things);
    }

    move_chips_to_match_game();
    for (int pile = 0; pile <= POT_PILE; ++pile) {
      auto chips = std::vector<int>();
      for (int chip = 0; chip < CHIP_COUNT; ++chip) {
        if (chip_pile[chip] == pile) chips.push_back(chip_thing(chip));
      }
      set_zone(pile == POT_PILE ? "pot" : chips_zone(pile), chips);
    }

    auto on_table = std::vector<int>();
    if (state.card_on_table != 0) {
      on_table.push_back(card_thing(state.card_on_table));
    }
    set_zone("table", on_table);

    auto deck = std::vector<int>();
    for (uint8_t card : state.deck) deck.push_back(card_thing(card));
    set_zone("deck", deck);

    save_to_json<Game_State>(state, SNAPSHOT_PATH);
  }

  // Leaving playground: the table is what the player arranged, so read it back
  // into the game.
  void update_game_from_table() override {
    table.is_drop_allowed = [](int, int, int) { return false; };

    Game_State& state = this->nt_game();

    auto zone_things = [&](const std::string& name) -> const std::vector<int>& {
      return table.things[find_thing(table, name)].children();
    };

    for (int player = 0; player < PLAYER_COUNT; ++player) {
      state.taken[player].clear();
      for (int thing : zone_things(cards_zone(player))) {
        state.taken[player].push_back((uint8_t)thing_card(thing));
      }
    }

    // A pile holds as many chips as the player has, and each chip remembers
    // the pile it was dragged into.
    for (int pile = 0; pile <= POT_PILE; ++pile) {
      const auto& chips =
        zone_things(pile == POT_PILE ? "pot" : chips_zone(pile));
      for (int thing : chips) chip_pile[thing - CARD_COUNT] = pile;
      if (pile == POT_PILE)
        state.chips_on_card = (uint8_t)chips.size();
      else
        state.chips[pile] = (uint8_t)chips.size();
    }

    const auto& on_table = zone_things("table");
    state.card_on_table =
      on_table.empty() ? 0 : (uint8_t)thing_card(on_table.front());

    state.deck.clear();
    for (int thing : zone_things("deck")) {
      state.deck.push_back((uint8_t)thing_card(thing));
    }
  }

  // Unused: with three seats the agents are built in make_seat_agent below.
  Agent* agent_opponent() override { return nullptr; }

  // One agent per seat. The local player uses the mouse; the other two search.
  Agent* make_seat_agent(const Menu_Result&, bool vs_ai) override {
    auto agents = std::vector<Agent*>();
    for (int player = 0; player < PLAYER_COUNT; ++player) {
      if (!vs_ai || player == this->bottom_player) {
        agents.push_back(&agent_ui);
        continue;
      }
      // The deck is face down, so each seat searches deals it cannot tell
      // apart from the real one and votes.
      // agents.push_back(new Agent_MCTS_Stochastic<Game_State>(
      //   /* num_samples          */ 32,
      //   /* num_iterations       */ 99999999,
      //   /* rollout_depth        */ 99999999,
      //   /* exploration_constant */ 1.41421356f,
      //   /* total_time_budget    */ 2.0,
      //   /* frame_time_budget    */ 1.0 / 120.0
      // ));
      agents.push_back(
        new Agent_Async(new Agent_Minimax_Stochastic<Game_State>(28, 16))
      );
    }
    return new Agent_Seats(agents);
  }

  std::vector<int> player_scores() const override {
    auto scores = std::vector<int>();
    for (int player = 0; player < PLAYER_COUNT; ++player) {
      scores.push_back(player_score(this->nt_game(), player));
    }
    return scores;
  }

  bool lower_score_wins() const override { return true; }
};

int main(int argc, char** argv) {
  auto options  = parse_play_args(argc, argv);
  auto game     = Game_State();
  auto agent_ui = No_Thanks_Agent_UI();
  auto giocamo  = No_Thanks_Giocamo(game, agent_ui);

  play_game(giocamo, options, "No Thanks!");
  return 0;
}
