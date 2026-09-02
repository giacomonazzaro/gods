#include <game/agent.h>
#include <game/game.h>
#include <game/mcts.h>
#include <game/minimax.h>
#include <giocamo/menu.h>
#include <giocamo/play.h>
#include <tabletop/config.h>
#include <tabletop/rendering.h>
#include <tabletop/tabletop.h>
#include <tabletop/ui.h>
#include <triplechess/ai.h>
#include <triplechess/gameplay.h>
#include <triplechess/models.h>

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>
#include <struct/imgui.h>  // for draw_editor_ui()
#include <struct/json.h>   // for to_json()

#include <algorithm>
#include <string>
#include <vector>

#include "agent_ui.h"
#include "ui.h"

// Square Things hold ids 0..BOARD_SIZE*BOARD_SIZE-1 (id == board index). The
// piece Things follow at PIECE_THING_BASE: a pool of one per piece that can
// be on the board at once (12, fixed — pieces never promote into a new one).
// The two rows that hold captured pieces come after them.
static const int PIECE_THING_BASE = triplechess::BOARD_SIZE *
                                    triplechess::BOARD_SIZE;
static const int PIECE_THING_COUNT  = 12;
static const int TAKEN_ROW_THING[2] = {
  PIECE_THING_BASE + PIECE_THING_COUNT,  // Player 0 pieces, left of the board.
  PIECE_THING_BASE + PIECE_THING_COUNT + 1,  // Player 1 pieces, right of it.
};

// How wide a row of captured pieces is, and how far apart the pieces sit in
// it.
static const float TAKEN_ROW_WIDTH  = 260.0f;
static const float TAKEN_ROW_SPREAD = 30.0f;

// Piece identity, kept across moves so a piece keeps its Thing as it travels
// and the renderer slides it. There is one board per process, so file-static
// is fine.
namespace {
int thing_for_square
  [triplechess::BOARD_SIZE *
   triplechess::BOARD_SIZE];  // Pool
                              // Thing on each square, or -1.
int
  square_of_thing[PIECE_THING_COUNT];  // Square each pool Thing sits on, or -1.
int value_of_thing[PIECE_THING_COUNT];  // Piece value each pool Thing shows, 0
                                        // if it has never held one.
}  // namespace

int triplechess_piece_thing_on_square(int square) {
  int pool_index = thing_for_square[square];
  return pool_index < 0 ? -1 : PIECE_THING_BASE + pool_index;
}

static Agent* make_minimax_agent() {
  return new Agent_Minimax<triplechess::Game_State>(
    7  // max_depth
  );
}

static Agent* make_mcts_agent() {
  auto* agent = new Agent_MCTS<triplechess::Game_State>(
    /* num_iterations       */ 9999999,
    /* rollout_depth        */ 40,
    /* exploration_constant */ 1.41421356f,
    /* time_budget_seconds  */ 1.0f
  );
  const int minimax_depth = 2;
  agent->leaf_evaluator =
    [minimax_depth](const triplechess::Game_State& state, int player) {
      const float             infinity = std::numeric_limits<float>::infinity();
      triplechess::Game_State copy = state;  // minimax needs a mutable copy.
      return minimax_detail::minimax(
        copy, minimax_depth, -infinity, infinity, player, [] { return false; }
      );
    };
  return agent;
}

// Triplechess on the table. The table is laid out once here; play_game sets the
// position up and drives the loop through these hooks.
struct Triplechess_Giocamo : Giocamo_With_History<triplechess::Game_State> {
  // --watch: the two bots play each other and we just spectate.
  bool watch = false;

  Triplechess_Giocamo(
    triplechess::Game_State& game, Triplechess_Agent_UI& agent_ui
  )
      : Giocamo_With_History<triplechess::Game_State>(game, agent_ui) {}

  triplechess::Game_State& triplechess_game() {
    return static_cast<triplechess::Game_State&>(game);
  }
  const triplechess::Game_State& triplechess_game() const {
    return static_cast<const triplechess::Game_State&>(game);
  }

  Triplechess_Agent_UI& triplechess_agent_ui() {
    return static_cast<Triplechess_Agent_UI&>(agent_ui);
  }

  // One square Thing per board slot (id == board index), PIECE_THING_COUNT
  // detached piece Things, then a screen-filling root that parents the
  // squares.
  void init_table() override {
    // A piece may be dropped on a square its owner could legally move it to
    // — that square itself if empty, or the piece standing there if it is a
    // capture or a push (dragging over an occupied square hovers the piece on
    // it, not the square underneath, so that piece's Thing is what has to
    // match here).
    table.is_drop_allowed = [this](int, int hovered_id, int thing_id) {
      if (thing_id < PIECE_THING_BASE ||
          thing_id >= PIECE_THING_BASE + PIECE_THING_COUNT) {
        return false;
      }
      int from_square = square_of_thing[thing_id - PIECE_THING_BASE];
      if (from_square < 0) return false;
      for (const triplechess::Move& move :
           triplechess::legal_moves(this->triplechess_game())) {
        if (move.from != from_square) continue;
        int dest_thing = triplechess_piece_thing_on_square(move.to);
        int container  = dest_thing >= 0 ? dest_thing : move.to;
        if (container == hovered_id) return true;
      }
      return false;
    };

    std::vector<Thing> squares = make_triplechess_squares();
    std::vector<int>   square_ids;
    for (Thing& square : squares) {
      // Ends up at 0..BOARD_SIZE*BOARD_SIZE-1 == row*BOARD_SIZE + col.
      square_ids.push_back(add_thing(table, std::move(square)));
    }

    // Piece Things: shape and color are set in update_table_from_game once a
    // piece's type and player are known.
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      Thing piece;
      piece.name         = "piece" + std::to_string(i);
      piece.border_color = {0, 0, 0, 255};
      piece.border_width = 4;
      piece.color = Color{0, 0, 0, 0};  // Set once the piece's value is known.
      table.things.push_back(piece);    // Lands at PIECE_THING_BASE + i.
    }

    // A row of captured pieces on each flank of the board, in root-local
    // coords. Player 0's captured pieces go on the left, player 1's on the
    // right.
    const float board_half = ((float)triplechess::BOARD_SIZE / 2.0f) *
                             (float)SCAMORRA_CELL;
    const float row_y    = -(float)SCAMORRA_CELL / 2.0f;
    Rectangle   left_row = {
      -(board_half + 20.0f + TAKEN_ROW_WIDTH),
      row_y,
      TAKEN_ROW_WIDTH,
      (float)SCAMORRA_CELL
    };
    Rectangle right_row = {
      board_half + 20.0f, row_y, TAKEN_ROW_WIDTH, (float)SCAMORRA_CELL
    };
    // Land at TAKEN_ROW_THING[0] and [1].
    add_thing(
      table,
      make_container_thing(
        left_row, TAKEN_ROW_SPREAD, 0.0f, true, "player0_taken"
      )
    );
    add_thing(
      table,
      make_container_thing(
        right_row, TAKEN_ROW_SPREAD, 0.0f, true, "player1_taken"
      )
    );

    auto root = create_table_root(
      tt::WINDOW_WIDTH, tt::WINDOW_HEIGHT, "tabletop/data/wood.png"
    );
    // Pieces are never root children — each one is a child of the square (or
    // captured-row) Thing it sits in — so root's own children never change
    // after this.
    root._children = square_ids;
    root._children.push_back(TAKEN_ROW_THING[0]);
    root._children.push_back(TAKEN_ROW_THING[1]);
    table.root = add_thing(table, std::move(root));

    int square_count = triplechess::BOARD_SIZE * triplechess::BOARD_SIZE;
    for (int square = 0; square < square_count; ++square)
      thing_for_square[square] = -1;
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      square_of_thing[i] = -1;
      value_of_thing[i]  = 0;
    }

    // Per-frame overlay: just the HUD. Picking up a piece, highlighting its
    // legal destinations, and dropping it are handled by
    // Triplechess_Agent_UI's gesture_map, through process_gestures.
    table.draw_callbacks[-1] = [this](const Table_State&, const Input&, bool) {
      draw_triplechess_hud(this->triplechess_game());
    };
  }

  // Reconcile the piece Things with the board: the moving piece keeps its
  // Thing (matched by value) and is re-parented onto the destination square
  // (a capacity-1 container), which is what makes the renderer slide it
  // there. A pushed piece is freed and re-matched the same way, which is
  // what makes it appear to hop one square further.
  void update_table_from_game() override {
    triplechess::Game_State& state = this->triplechess_game();
    int square_count = triplechess::BOARD_SIZE * triplechess::BOARD_SIZE;

    // A drag-and-drop onto a capture or a push nests the moving piece under
    // the piece standing on the destination square for one frame (that is
    // what the cursor is actually hovering — see is_drop_allowed above), so
    // every piece starts this rebuild with no children; the loops below are
    // what give a square (or a captured row) its piece back.
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      table.things[PIECE_THING_BASE + i]._children.clear();
    }

    // Release every Thing whose square no longer holds its piece; remember
    // them as free so the squares that still need a piece can reuse them.
    int freed[PIECE_THING_COUNT];
    int freed_count = 0;
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      int square = square_of_thing[i];
      if (square < 0) continue;
      int row = square / triplechess::BOARD_SIZE;
      int col = square % triplechess::BOARD_SIZE;
      if (state.board[row][col] != value_of_thing[i]) {
        thing_for_square[square] = -1;
        square_of_thing[i]       = -1;
        freed[freed_count++]     = i;
      }
    }

    // Fill each square that needs a piece. Prefer a freed Thing of the same
    // value (the piece that actually moved, or was pushed — it slides over),
    // then any freed Thing, then a piece taken earlier that is back on the
    // board (an undo), then a spare (first placement).
    bool used[PIECE_THING_COUNT];
    for (int k = 0; k < freed_count; ++k) used[k] = false;
    for (int square = 0; square < square_count; ++square) {
      int row   = square / triplechess::BOARD_SIZE;
      int col   = square % triplechess::BOARD_SIZE;
      int value = state.board[row][col];
      if (value == triplechess::EMPTY || thing_for_square[square] != -1)
        continue;

      int chosen = -1;
      for (int k = 0; k < freed_count; ++k) {
        if (!used[k] && value_of_thing[freed[k]] == value) {
          chosen  = freed[k];
          used[k] = true;
          break;
        }
      }
      if (chosen < 0) {
        for (int k = 0; k < freed_count; ++k) {
          if (!used[k]) {
            chosen  = freed[k];
            used[k] = true;
            break;
          }
        }
      }
      if (chosen < 0) {
        for (int i = 0; i < PIECE_THING_COUNT; ++i) {
          if (square_of_thing[i] < 0 && value_of_thing[i] == value) {
            chosen = i;
            break;
          }
        }
      }
      if (chosen < 0) {
        for (int i = 0; i < PIECE_THING_COUNT; ++i) {
          if (square_of_thing[i] < 0 && value_of_thing[i] == 0) {
            chosen = i;
            break;
          }
        }
      }
      if (chosen < 0)
        continue;  // Pool exhausted — cannot happen with 12
                   // pieces.

      value_of_thing[chosen]   = value;
      square_of_thing[chosen]  = square;
      thing_for_square[square] = chosen;
      Thing& piece             = table.things[PIECE_THING_BASE + chosen];
      piece.shape = triplechess_piece_shape(triplechess::piece_type(value));
      piece.color = triplechess_piece_color(value);
      // A square holds at most one piece, so its child sits centered on it
      // (local origin) — reset here because a piece coming back from a
      // captured row still carries that row's spread-out local transform.
      piece.transform = Transform2D{};
    }

    // Every square's child is whichever piece Thing (if any) update_table
    // just matched to it — the single source of truth for what is on the
    // board, replacing anything left over from a drag.
    for (int square = 0; square < square_count; ++square) {
      int pool_index = thing_for_square[square];
      table.things[square]._children =
        pool_index < 0 ? std::vector<int>{}
                       : std::vector<int>{PIECE_THING_BASE + pool_index};
    }

    // A Thing that holds a piece but sits on no square was captured. It keeps
    // its appearance and goes to the row for its player, and the renderer
    // slides it there from the square it was captured on.
    auto taken = std::vector<std::vector<int>>(2);
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      int value = value_of_thing[i];
      if (value == triplechess::EMPTY) continue;  // Never held a piece.
      if (square_of_thing[i] < 0) {
        taken[triplechess::piece_color(value)].push_back(PIECE_THING_BASE + i);
      }
    }

    for (int color = 0; color < 2; ++color) {
      table.things[TAKEN_ROW_THING[color]]._children = taken[color];
      update_children_positions(TAKEN_ROW_THING[color], table, false);
    }
  }

  // update_table_from_game rebuilds the whole tree from the board after every
  // real move and snaps a rejected drag back on its own, so the table never
  // holds an arrangement the game doesn't already have.
  void update_game_from_table() override {}

  // Watch mode: player 1 is the MCTS bot. Otherwise the human plays against
  // the minimax bot.
  Agent* agent_opponent() override {
    // if (watch)
    // return new Agent_Async(make_mcts_agent());
    return new Agent_Async(make_minimax_agent());
  }

  // Watch mode: player 0 is the minimax bot instead of the player.
  Agent* agent_player() override {
    // if (watch) return new Agent_Async(make_minimax_agent());
    // return new Agent_Async(make_mcts_agent());

    return &agent_ui;
  }

  std::vector<int> player_scores() const override {
    return {
      triplechess::compute_player_score(this->triplechess_game(), 0),
      triplechess::compute_player_score(this->triplechess_game(), 1),
    };
  }
};

int main(int argc, char** argv) {
  auto options = parse_play_args(argc, argv);

  auto game     = triplechess::Game_State();
  auto agent_ui = Triplechess_Agent_UI();
  auto giocamo  = Triplechess_Giocamo(game, agent_ui);

  for (int i = 1; i < argc; ++i) {
    if (std::string(argv[i]) == "--watch") giocamo.watch = true;
  }
  // Nothing to choose when both seats are bots.
  if (giocamo.watch) options.skip_menu = true;

  play_game(giocamo, options, "Triplechess");
  return 0;
}
