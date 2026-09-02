#include <chess/ai.h>
#include <chess/gameplay.h>
#include <chess/models.h>
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

// raylib last: its color macros (RED/GREEN/BLUE) would expand inside enums
// otherwise.
#include <raylib.h>

#include <algorithm>
#include <string>
#include <vector>

#include <struct/imgui.h>  // for draw_editor_ui()
#include <struct/json.h>   // for to_json()

#include "agent_ui.h"
#include "ui.h"

// Square Things hold ids 0..63 (id == board index). The piece Things follow at
// 64..95: a pool of 32, one per piece that can be on the board at once. The two
// rows that hold the taken pieces come after them.
static const int PIECE_THING_BASE  = 64;
static const int PIECE_THING_COUNT = 32;
static const int TAKEN_ROW_THING[2] = {
  PIECE_THING_BASE + PIECE_THING_COUNT,      // White pieces, left of the board.
  PIECE_THING_BASE + PIECE_THING_COUNT + 1,  // Black pieces, right of it.
};

// How wide a row of taken pieces is, and how far apart the pieces sit in it.
// A full row of 16 does not fit at this spacing, so they overlap — the row
// shrinks the spacing itself once they no longer fit.
static const float TAKEN_ROW_WIDTH  = 470.0f;
static const float TAKEN_ROW_SPREAD = 30.0f;

// Piece identity, kept across moves so a piece keeps its Thing as it travels
// and the renderer slides it. There is one board per process, so file-static is
// fine.
namespace {
int thing_for_square[64];  // Pool Thing on each square, or -1.
int
  square_of_thing[PIECE_THING_COUNT];  // Square each pool Thing sits on, or -1.
int value_of_thing[PIECE_THING_COUNT];  // Piece value each pool Thing shows, 0
                                        // if it has never held one.
}  // namespace

int chess_piece_thing_on_square(int square) {
  int pool_index = thing_for_square[square];
  return pool_index < 0 ? -1 : PIECE_THING_BASE + pool_index;
}

// Image file for a piece value, e.g. white knight -> "...pieces/wN.png". The
// "w"/"b" prefix is the color and the glyph letter is the piece type.
static std::string piece_image_path(int value) {
  std::string color = chess::piece_color(value) == 0 ? "w" : "b";
  return "chess_app/data/pieces/" + color + chess_piece_glyph(value) + ".png";
}

// Iterative-deepening alpha-beta with a wall-clock budget: it plays much more
// soundly than MCTS in this tactical game, deepening the search until the time
// runs out and playing the best move from the deepest completed depth.
static Agent* make_minimax_agent() {
  return new Agent_Minimax<chess::Game_State>(
    6  // max_depth
  );
}

// MCTS whose leaves are scored by a shallow alpha-beta search.
static Agent* make_mcts_agent() {
  auto* agent = new Agent_MCTS<chess::Game_State>(
    /* num_iterations       */ 9999999,
    /* rollout_depth        */ 40,
    /* exploration_constant */ 1.41421356f,
    /* time_budget_seconds  */ 8.0f
  );
  const int minimax_depth = 2;
  agent->leaf_evaluator =
    [minimax_depth](const chess::Game_State& state, int player) {
      const float       infinity = std::numeric_limits<float>::infinity();
      chess::Game_State copy     = state;  // minimax needs a mutable copy.
      return minimax_detail::minimax(
        copy, minimax_depth, -infinity, infinity, player, [] { return false; }
      );
    };
  return agent;
}

// Chess on the table. The table is laid out once here; play_game sets the
// position up and drives the loop through these hooks.
struct Chess_Giocamo : Giocamo_With_History<chess::Game_State> {
  // --watch: the two bots play each other (White = minimax, Black = MCTS) and
  // we just spectate.
  bool watch = false;

  Chess_Giocamo(chess::Game_State& game, Chess_Agent_UI& agent_ui)
      : Giocamo_With_History<chess::Game_State>(game, agent_ui) {}

  chess::Game_State& chess_game() {
    return static_cast<chess::Game_State&>(game);
  }
  const chess::Game_State& chess_game() const {
    return static_cast<const chess::Game_State&>(game);
  }

  Chess_Agent_UI& chess_agent_ui() {
    return static_cast<Chess_Agent_UI&>(agent_ui);
  }

  // One square Thing per board slot (id == board index), 32 detached piece
  // Things, then a screen-filling root that parents the squares.
  void init_table() override {
    // A piece may be dropped on a square its owner could legally move it to
    // — that square itself if empty, or the piece standing there if it is a
    // capture (dragging over an occupied square hovers the piece on it, not
    // the square underneath, so that piece's Thing is what has to match
    // here).
    table.is_drop_allowed = [this](int, int hovered_id, int thing_id) {
      if (thing_id < PIECE_THING_BASE ||
          thing_id >= PIECE_THING_BASE + PIECE_THING_COUNT) {
        return false;
      }
      int from_square = square_of_thing[thing_id - PIECE_THING_BASE];
      if (from_square < 0) return false;
      for (const chess::Move& move :
           chess::legal_moves(this->chess_game())) {
        if (move.from != from_square) continue;
        int dest_thing = chess_piece_thing_on_square(move.to);
        int container   = dest_thing >= 0 ? dest_thing : move.to;
        if (container == hovered_id) return true;
      }
      return false;
    };

    std::vector<Thing> squares = make_chess_squares();
    std::vector<int>   square_ids;
    for (Thing& square : squares) {
      // Ends up at 0..63 == row*8 + col.
      square_ids.push_back(add_thing(table, std::move(square)));
    }

    // Piece Things: a square body that draws a piece image (set in
    // update_table_from_game). A zero corner radius keeps the renderer from
    // rounding the texture. Each one is parented onto the square it stands
    // on (see update_table_from_game), which is what draws it on top of that
    // square and slides it when the square changes.
    Shape piece_shape =
      Shape_Rectangle{{(float)CHESS_CELL, (float)CHESS_CELL}, 0.0f};
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      Thing piece;
      piece.name  = "piece" + std::to_string(i);
      // Lands at PIECE_THING_BASE + i.
      piece.shape = piece_shape;
      piece.color = Color{0, 0, 0, 0};  // Only used if the image fails to load.
      table.things.push_back(piece);
    }

    // A row of taken pieces on each flank of the board, in root-local coords
    // (the root is centered, so the board spans -360..360). White's taken
    // pieces go on the left, black's on the right.
    const float board_half = 4.0f * (float)CHESS_CELL;
    const float row_y      = -(float)CHESS_CELL / 2.0f;
    Rectangle   white_row  = {
      -(board_half + 20.0f + TAKEN_ROW_WIDTH),
      row_y,
      TAKEN_ROW_WIDTH,
      (float)CHESS_CELL
    };
    Rectangle black_row = {
      board_half + 20.0f, row_y, TAKEN_ROW_WIDTH, (float)CHESS_CELL
    };
    // Land at TAKEN_ROW_THING[0] and [1].
    add_thing(
      table,
      make_container_thing(
        white_row, TAKEN_ROW_SPREAD, 0.0f, true, "white_taken"
      )
    );
    add_thing(
      table,
      make_container_thing(
        black_row, TAKEN_ROW_SPREAD, 0.0f, true, "black_taken"
      )
    );

    auto root = create_table_root(
      tt::WINDOW_WIDTH, tt::WINDOW_HEIGHT, "tabletop/data/wood.png"
    );
    // Pieces are never root children — each one is a child of the square (or
    // taken-row) Thing it sits in — so root's own children never change
    // after this.
    root._children = square_ids;
    root._children.push_back(TAKEN_ROW_THING[0]);
    root._children.push_back(TAKEN_ROW_THING[1]);
    table.root = add_thing(table, std::move(root));

    for (int square = 0; square < 64; ++square) thing_for_square[square] = -1;
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      square_of_thing[i] = -1;
      value_of_thing[i]  = 0;
    }

    // Per-frame overlay: just the HUD. Picking up a piece, highlighting its
    // legal destinations, and dropping it are handled by Chess_Agent_UI's
    // gesture_map, through process_gestures.
    table.draw_callbacks[-1] = [this](const Table_State&, const Input&, bool) {
      draw_chess_hud(this->chess_game());
    };
  }

  // Reconcile the piece Things with the board: the moving piece keeps its Thing
  // (matched by value) and is re-parented onto the destination square (a
  // capacity-1 container), which is what makes the renderer slide it there.
  void update_table_from_game() override {
    chess::Game_State& state = this->chess_game();

    // A drag-and-drop onto a capture nests the moving piece under the piece
    // standing on the destination square for one frame (that is what the
    // cursor is actually hovering — see is_drop_allowed above), and castling
    // moves the rook without going through a drag at all, so every piece
    // starts this rebuild with no children; the loops below are what give a
    // square (or a taken row) its piece back.
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      table.things[PIECE_THING_BASE + i]._children.clear();
    }

    // Release every Thing whose square no longer holds its piece; remember them
    // as free so the squares that still need a piece can reuse them.
    int freed[PIECE_THING_COUNT];
    int freed_count = 0;
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      int square = square_of_thing[i];
      if (square < 0) continue;
      if (state.board[square / 8][square % 8] != value_of_thing[i]) {
        thing_for_square[square] = -1;
        square_of_thing[i]       = -1;
        freed[freed_count++]     = i;
      }
    }

    // Fill each square that needs a piece. Prefer a freed Thing of the same
    // value (the piece that actually moved — it slides over), then a piece
    // taken earlier that is back on the board (an undo brings a captured
    // piece back before its own square is processed, so this has to come
    // before the "any freed Thing" check below — otherwise that check could
    // grab a freed Thing of the wrong value for this square, leaving no
    // freed Thing left for the square that actually needs it), then any
    // freed Thing (a promotion reuses the pawn's Thing), then a spare (first
    // placement).
    bool used[PIECE_THING_COUNT];
    for (int k = 0; k < freed_count; ++k) used[k] = false;
    for (int square = 0; square < 64; ++square) {
      int value = state.board[square / 8][square % 8];
      if (value == 0 || thing_for_square[square] != -1) continue;

      int chosen = -1;
      for (int k = 0; k < freed_count; ++k) {
        if (!used[k] && value_of_thing[freed[k]] == value) {
          chosen  = freed[k];
          used[k] = true;
          break;
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
          if (square_of_thing[i] < 0 && value_of_thing[i] == 0) {
            chosen = i;
            break;
          }
        }
      }
      if (chosen < 0) continue;  // Pool exhausted — cannot happen with 32
                                 // pieces.

      value_of_thing[chosen]   = value;
      square_of_thing[chosen]  = square;
      thing_for_square[square] = chosen;
      Thing& piece             = table.things[PIECE_THING_BASE + chosen];
      piece.image_path         = piece_image_path(value);
      // A square holds at most one piece, so its child sits centered on it
      // (local origin) — reset here because a piece coming back from a taken
      // row still carries that row's spread-out local transform.
      piece.transform = Transform2D{};
    }

    // Every square's child is whichever piece Thing (if any) update_table
    // just matched to it — the single source of truth for what is on the
    // board, replacing anything left over from a drag or a castle.
    for (int square = 0; square < 64; ++square) {
      int pool_index = thing_for_square[square];
      table.things[square]._children =
        pool_index < 0 ? std::vector<int>{}
                       : std::vector<int>{PIECE_THING_BASE + pool_index};
    }

    // A Thing that holds a piece but sits on no square was taken. It keeps its
    // image and goes to the row for its colour; the renderer slides it there
    // from the square it was taken on.
    auto taken = std::vector<std::vector<int>>(2);
    for (int i = 0; i < PIECE_THING_COUNT; ++i) {
      int value = value_of_thing[i];
      if (value == 0) continue;  // Never held a piece.
      if (square_of_thing[i] < 0) {
        taken[chess::piece_color(value)].push_back(PIECE_THING_BASE + i);
      }
    }

    // Strongest piece first, so a row reads the same however the Things were
    // handed out.
    for (int color = 0; color < 2; ++color) {
      std::sort(
        taken[color].begin(),
        taken[color].end(),
        [](int a, int b) {
          return chess::piece_type(value_of_thing[a - PIECE_THING_BASE]) >
                 chess::piece_type(value_of_thing[b - PIECE_THING_BASE]);
        }
      );
      table.things[TAKEN_ROW_THING[color]]._children = taken[color];
      update_children_positions(TAKEN_ROW_THING[color], table, false);
    }
  }

  // update_table_from_game rebuilds the whole tree from the board after every
  // real move and snaps a rejected drag back on its own, so the table never
  // holds an arrangement the game doesn't already have.
  void update_game_from_table() override {}

  // Watch mode: Black is the MCTS bot. Otherwise the human plays against the
  // minimax bot.
  Agent* agent_opponent() override {
    if (watch) return new Agent_Async(make_mcts_agent());
    return new Agent_Async(make_minimax_agent());
  }

  // Watch mode: White is the minimax bot instead of the player.
  Agent* agent_player() override {
    if (watch) return new Agent_Async(make_minimax_agent());
    return &agent_ui;
  }

  std::vector<int> player_scores() const override {
    return {
      chess::compute_player_score(this->chess_game(), 0),
      chess::compute_player_score(this->chess_game(), 1),
    };
  }
};

int main(int argc, char** argv) {
  auto options = parse_play_args(argc, argv);

  auto game     = chess::Game_State();
  auto agent_ui = Chess_Agent_UI();
  auto giocamo  = Chess_Giocamo(game, agent_ui);

  for (int i = 1; i < argc; ++i) {
    if (std::string(argv[i]) == "--watch") giocamo.watch = true;
  }
  // Nothing to choose when both seats are bots.
  if (giocamo.watch) options.skip_menu = true;

  play_game(giocamo, options, "Chess");
  return 0;
}
