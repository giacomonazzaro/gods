#include <air_land_sea/gameplay.h>
#include <air_land_sea/models.h>
#include <game/agent.h>
#include <game/game.h>
#include <game/mcts.h>
#include <game/minimax.h>
#include <game/stochastic.h>
#include <giocamo/menu.h>
#include <giocamo/play.h>
#include <struct/imgui.h>  // for draw_editor_ui()
#include <tabletop/config.h>
#include <tabletop/rendering.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

#include <string>
#include <vector>

#include "agent_ui.h"
#include "ui.h"

using namespace air_land_sea;

// The three theaters stand side by side across the middle of the screen. Each
// player's cards for a theater lie in a row on their side of it, each new card
// to the right of and on top of the ones already there, so a covered card still
// shows its left edge with its strength on it. The hand is along the player's
// edge of the screen, the opponent's along the opposite one.
static const float     COLUMN_X[THEATER_COUNT] = {-540.0f, 0.0f, 540.0f};
static constexpr float ROW_Y                   = 150.0f;
static constexpr float ROW_WIDTH               = 380.0f;
static constexpr float ROW_SPREAD              = 46.0f;
static constexpr float HAND_Y                  = 371.0f;
static constexpr float HAND_WIDTH              = 760.0f;
static constexpr float HAND_SPREAD             = 160.0f;
static constexpr float THEATER_WIDTH           = 200.0f;
static constexpr float THEATER_HEIGHT          = 70.0f;
static constexpr int   COUNTER_SIZE            = 80;
static constexpr float STRENGTH_X = -235.0f;  // Relative to the column.
static constexpr float STRENGTH_Y = 55.0f;
static constexpr float POINTS_X   = -800.0f;
static constexpr float POINTS_Y   = 180.0f;
static constexpr float DECK_X     = 740.0f;
static constexpr float DECK_Y     = 371.0f;

// Where the debug snapshot of the game is written and read.
static const std::string SNAPSHOT_PATH = "data/debug_game_state.json";

// Thing ids. The 18 cards come first, so a card's id is its card index.
static int theater_bar_thing(int position) { return CARD_COUNT + position; }
static int points_thing(int player) {
  return CARD_COUNT + THEATER_COUNT + player;
}
static int strength_thing(int position, int player) {
  return CARD_COUNT + THEATER_COUNT + 2 + position * 2 + player;
}

static Rectangle centered(float x, float y, float width, float height) {
  return Rectangle{x - width / 2.0f, y - height / 2.0f, width, height};
}

static std::string zone_name(int player, const char* zone) {
  return "p" + std::to_string(player) + "_" + zone;
}

static std::string side_zone_name(int player, int position) {
  return "p" + std::to_string(player) + "_t" + std::to_string(position);
}

static std::string strength_zone_name(int player, int position) {
  return "p" + std::to_string(player) + "_s" + std::to_string(position);
}

// Every place a thing can sit. The bottom player's zones are below the middle
// of the screen and the other player's mirror them above it.
static std::vector<Thing> make_zones(int bottom_player) {
  const float card_width  = (float)tt::CARD_WIDTH;
  const float card_height = (float)tt::CARD_HEIGHT;

  auto zones = std::vector<Thing>();
  for (int player = 0; player < 2; ++player) {
    // +1 for the player at the bottom of the screen, -1 for the other one.
    const float side = player == bottom_player ? 1.0f : -1.0f;

    zones.push_back(make_container_thing(
      centered(0.0f, side * HAND_Y, HAND_WIDTH, card_height),
      HAND_SPREAD,
      0.0f,
      true,
      zone_name(player, "hand")
    ));
    zones.push_back(make_container_thing(
      centered(
        POINTS_X, side * POINTS_Y, (float)COUNTER_SIZE, (float)COUNTER_SIZE
      ),
      0.0f,
      0.0f,
      true,
      zone_name(player, "points")
    ));

    for (int position = 0; position < THEATER_COUNT; ++position) {
      zones.push_back(make_container_thing(
        centered(COLUMN_X[position], side * ROW_Y, ROW_WIDTH, card_height),
        ROW_SPREAD,
        0.0f,
        true,
        side_zone_name(player, position)
      ));
      zones.push_back(make_container_thing(
        centered(
          COLUMN_X[position] + STRENGTH_X,
          side * STRENGTH_Y,
          (float)COUNTER_SIZE,
          (float)COUNTER_SIZE
        ),
        0.0f,
        0.0f,
        true,
        strength_zone_name(player, position)
      ));
    }
  }

  for (int position = 0; position < THEATER_COUNT; ++position) {
    zones.push_back(make_container_thing(
      centered(COLUMN_X[position], 0.0f, THEATER_WIDTH, THEATER_HEIGHT),
      0.0f,
      0.0f,
      true,
      "t" + std::to_string(position)
    ));
  }

  // The deck sits face down in the corner, out of the way of the theaters.
  zones.push_back(make_container_thing(
    centered(DECK_X, DECK_Y, card_width, card_height),
    0.0f,
    -3.0f,
    false,
    "deck"
  ));
  return zones;
}

// Air, Land, & Sea on the table. The table is laid out once here; play_game
// deals the game and drives the loop through these hooks.
struct Air_Land_Sea_Giocamo : Giocamo_With_History<Game_State> {
  Air_Land_Sea_Giocamo(Game_State& game, Air_Land_Sea_Agent_UI& agent_ui)
      : Giocamo_With_History<Game_State>(game, agent_ui) {}

  Game_State&       als_game() { return static_cast<Game_State&>(game); }
  const Game_State& als_game() const {
    return static_cast<const Game_State&>(game);
  }

  void init_table() override {
    table.is_drop_allowed = [](int, int, int) { return false; };

    // The seat play_game gave the local player is what the UI shows a hand and
    // a face-down card to.
    auto& player_ui      = static_cast<Air_Land_Sea_Agent_UI&>(agent_ui);
    player_ui.local_seat = this->bottom_player;
    player_ui.hot_seat   = this->hot_seat;

    // One Thing per card; ids match the game's card indices.
    for (int card = 0; card < CARD_COUNT; ++card) {
      table.things.push_back(make_card());
      table.draw_callbacks[card] = make_card_draw_callback(
        this->als_game(), card, this->bottom_player, this->hot_seat
      );
    }

    // The three theater cards. Which theater each one shows changes between
    // battles, so its color and name are set in update_table_from_game.
    for (int position = 0; position < THEATER_COUNT; ++position) {
      auto bar     = Thing();
      bar.shape    = rectangle_shape({THEATER_WIDTH, THEATER_HEIGHT});
      bar.capacity = 0;
      table.things.push_back(std::move(bar));
      table.draw_callbacks[theater_bar_thing(position)] =
        make_theater_draw_callback(this->als_game(), position);
    }

    // Victory points and the strength each player has in each theater are
    // counters: the Thing draws its own value.
    for (int player = 0; player < 2; ++player) {
      auto counter    = Thing();
      counter.shape   = circle_shape((float)COUNTER_SIZE);
      counter.color   = {190, 160, 40, 255};
      counter.counter = {0, 0, POINTS_TO_WIN};
      table.things.push_back(std::move(counter));
    }
    for (int position = 0; position < THEATER_COUNT; ++position) {
      for (int player = 0; player < 2; ++player) {
        auto counter    = Thing();
        counter.shape   = circle_shape((float)COUNTER_SIZE);
        counter.color   = {45, 45, 55, 255};
        counter.counter = {0, 0, 40};
        table.things.push_back(std::move(counter));
      }
    }

    auto zone_ids = std::vector<int>();
    for (Thing& zone : make_zones(this->bottom_player)) {
      zone_ids.push_back(add_thing(table, std::move(zone)));
    }

    // Empty texture path: the table is drawn with root.color.
    auto root      = create_table_root(
      (int)table.window_size().x, (int)table.window_size().y, ""
    );
    root._children = zone_ids;
    root.color     = {0, 0, 0, 0};
    table.root     = add_thing(table, std::move(root));

    table.draw_callbacks[-1] = [this](const Table_State&, const Input&, bool) {
      draw_air_land_sea_hud(this->als_game(), this->bottom_player);
    };
  }

  // Every zone holds the cards the game says it holds, and a hand is only face
  // up for the player it belongs to.
  void update_table_from_game() override {
    Game_State& state = this->als_game();

    // Clicking a card also starts dragging it, and the card the player just
    // clicked is about to change zone. End the drag first, or the layout would
    // look for it in the zone it has already left.
    table.drag_state = Drag_State();

    for (int card = 0; card < CARD_COUNT; ++card) {
      table.things[card].color   = theater_color(card_theater(card));
      table.things[card].face_up = true;
    }
    for (const Placement& placement : state.board) {
      table.things[placement.card].face_up = !placement.face_down;
    }

    auto set_zone =
      [&](const std::string& name, const std::vector<int>& things) {
        const int zone               = find_thing(table, name);
        table.things[zone]._children = things;
        update_children_positions(zone, table, false);
      };

    for (int player = 0; player < 2; ++player) {
      const auto& hand = state.hands[player];
      set_zone(zone_name(player, "hand"), {hand.begin(), hand.end()});
      // You always see your own hand; the opponent's is face down unless both
      // players share this screen.
      table.things[find_thing(table, zone_name(player, "hand"))].face_up =
        player == this->bottom_player || this->hot_seat;

      for (int position = 0; position < THEATER_COUNT; ++position) {
        auto cards = std::vector<int>();
        for (const Placement& placement : state.board) {
          if (placement.owner != player) continue;
          if (placement.position != position) continue;
          cards.push_back(placement.card);
        }
        set_zone(side_zone_name(player, position), cards);

        const int counter = strength_thing(position, player);
        table.things[counter].counter.value =
          side_strength(state, position, player);
        set_zone(strength_zone_name(player, position), {counter});
      }

      table.things[points_thing(player)].counter.value = state.points[player];
      set_zone(zone_name(player, "points"), {points_thing(player)});
    }

    for (int position = 0; position < THEATER_COUNT; ++position) {
      const int bar           = theater_bar_thing(position);
      table.things[bar].color = theater_color(state.theaters[position]);
      set_zone("t" + std::to_string(position), {bar});
    }

    set_zone("deck", {state.deck.begin(), state.deck.end()});

    save_to_json<Game_State>(state, SNAPSHOT_PATH);
  }

  // Leaving playground: the table is what the player arranged, so read it back
  // into the game. Card Things carry the game's card indices, so a zone's
  // children are the cards of that zone.
  void update_game_from_table() override {
    table.is_drop_allowed = [](int, int, int) { return false; };

    Game_State& state = this->als_game();

    auto zone_things = [&](const std::string& name) -> const std::vector<int>& {
      return table.things[find_thing(table, name)].children();
    };

    state.board.clear();
    for (int player = 0; player < 2; ++player) {
      const auto& hand = zone_things(zone_name(player, "hand"));
      state.hands[player].assign(hand.begin(), hand.end());

      for (int position = 0; position < THEATER_COUNT; ++position) {
        for (int card : zone_things(side_zone_name(player, position))) {
          state.board.push_back(
            Placement{
              (uint8_t)card,
              (uint8_t)position,
              (uint8_t)player,
              (uint8_t)(table.things[card].face_up ? 0 : 1)
            }
          );
        }
      }
      state.points[player] =
        (uint8_t)table.things[points_thing(player)].counter.value;
    }

    const auto& deck = zone_things("deck");
    state.deck.assign(deck.begin(), deck.end());
  }

  Agent* agent_opponent() override {
    return new Agent_Minimax_Stochastic<Game_State>(5);
    return new Agent_MCTS_Stochastic<Game_State>(
      /* num_samples          */ 16,
      /* num_iterations       */ 99999999,
      /* rollout_depth        */ 0,
      /* exploration_constant */ 1.41421356f,
      /* total_time_budget    */ 3.0,
      /* frame_time_budget    */ 1.0 / 60.0
    );
  }

  std::vector<int> player_scores() const override {
    return {
      compute_player_score(this->als_game(), 0),
      compute_player_score(this->als_game(), 1),
    };
  }
};

int main(int argc, char** argv) {
  auto options  = parse_play_args(argc, argv);
  auto game     = Game_State();
  auto agent_ui = Air_Land_Sea_Agent_UI();
  auto giocamo  = Air_Land_Sea_Giocamo(game, agent_ui);

  play_game(giocamo, options, "Air, Land, & Sea");
  return 0;
}
