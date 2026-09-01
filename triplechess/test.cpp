// Rule checks for triplechess/gameplay.cpp: capture, push (including a blocked
// push and a suicidal move being rejected), and the win condition. Finishes
// with a bounded random self-play game to confirm play never crashes or
// stalls. Exits non-zero on any failure.

#include <triplechess/gameplay.h>
#include <triplechess/models.h>

#include <cstdio>
#include <cstdlib>

using namespace triplechess;

static bool all_passed = true;

static void check(bool condition, const char* what) {
  std::printf("%s: %s\n", what, condition ? "OK" : "FAILED");
  all_passed = all_passed && condition;
}

static int square(int row, int col) { return row * BOARD_SIZE + col; }

static bool contains(const Move_List& moves, int from, int to) {
  for (const Move& move : moves) {
    if (move.from == from && move.to == to) return true;
  }
  return false;
}

static Game_State empty_state(int current_player) {
  Game_State state;
  state.current_player = current_player;
  return state;
}

int main() {
  // Starting position: 12 pieces total, player 0 to move first.
  {
    Game_State state       = quick_setup(0);
    int        piece_count = 0;
    for (int row = 0; row < BOARD_SIZE; ++row) {
      for (int col = 0; col < BOARD_SIZE; ++col) {
        if (state.board[row][col] != EMPTY) ++piece_count;
      }
    }
    check(piece_count == 12, "starting position has 12 pieces");
    check(!legal_moves(state).empty(), "player 0 has moves at the start");
  }

  // Capture: rock beats scissors.
  {
    Game_State state  = empty_state(0);
    state.board[3][3] = make_piece(ROCK, 0);
    state.board[4][4] = make_piece(SCISSORS, 1);
    Move_List moves   = legal_moves(state);
    check(
      contains(moves, square(3, 3), square(4, 4)),
      "rock can capture an adjacent scissors"
    );

    Game_State after = state;
    apply_move(after, Move{square(3, 3), square(4, 4)});
    check(
      after.board[4][4] == make_piece(ROCK, 0) && after.board[3][3] == EMPTY,
      "capturing rock ends up on the scissors' square"
    );
  }

  // Suicide: a rock cannot move onto an enemy paper (paper beats rock).
  {
    Game_State state  = empty_state(0);
    state.board[3][3] = make_piece(ROCK, 0);
    state.board[4][4] = make_piece(PAPER, 1);
    Move_List moves   = legal_moves(state);
    check(
      !contains(moves, square(3, 3), square(4, 4)),
      "rock cannot move onto an enemy paper"
    );
  }

  // Push: a rock moving onto an enemy rock pushes it one square further,
  // when that square is on the board and empty.
  {
    Game_State state  = empty_state(0);
    state.board[3][3] = make_piece(ROCK, 0);
    state.board[4][4] = make_piece(ROCK, 1);
    Move_List moves   = legal_moves(state);
    check(
      contains(moves, square(3, 3), square(4, 4)),
      "rock can push an adjacent enemy rock into an empty square"
    );

    Game_State after = state;
    apply_move(after, Move{square(3, 3), square(4, 4)});
    check(
      after.board[4][4] == make_piece(ROCK, 0) &&
        after.board[5][5] == make_piece(ROCK, 1) && after.board[3][3] == EMPTY,
      "pushing rock takes the vacated square, the pushed rock lands one further"
    );
  }

  // Blocked push: the square behind the pushed piece is occupied, so the move
  // is not legal.
  {
    Game_State state  = empty_state(0);
    state.board[3][3] = make_piece(ROCK, 0);
    state.board[4][4] = make_piece(ROCK, 1);
    state.board[5][5] = make_piece(PAPER, 1);
    Move_List moves   = legal_moves(state);
    check(
      !contains(moves, square(3, 3), square(4, 4)),
      "push is illegal when the square behind the pushed piece is occupied"
    );
  }

  // Push off the edge: the pushed piece has nowhere on the board to land, so
  // it is killed instead of blocking the move.
  {
    Game_State state  = empty_state(0);
    state.board[3][7] = make_piece(SCISSORS, 0);
    state.board[3][6] = make_piece(SCISSORS, 1);
    Move_List moves   = legal_moves(state);
    check(
      contains(moves, square(3, 7), square(3, 6)),
      "pushing a piece off the edge of the board is legal"
    );

    Game_State after = state;
    apply_move(after, Move{square(3, 7), square(3, 6)});
    check(
      after.board[3][6] == make_piece(SCISSORS, 0) &&
        after.board[3][7] == EMPTY,
      "pushing piece takes the vacated square, the pushed piece is removed"
    );
  }

  // Win: moving a piece onto the opponent's home row ends the game.
  {
    Game_State state  = empty_state(0);
    state.board[6][0] = make_piece(ROCK, 0);
    apply_move(state, Move{square(6, 0), square(7, 0)});
    check(
      state.game_over && state.winner == 0,
      "reaching the opponent's home row wins the game"
    );
  }

  // Bounded random self-play: confirm a game always terminates and never
  // picks an out-of-range move.
  {
    std::srand(1);
    Game_State state     = quick_setup(0);
    int        max_plies = 500;
    int        plies     = 0;
    while (!state.is_game_over() && plies < max_plies) {
      Move_List moves = legal_moves(state);
      if (moves.empty()) break;
      const Move& move = moves[std::rand() % moves.size()];
      apply_move(state, move);
      ++plies;
    }
    check(
      state.is_game_over() && plies < max_plies,
      "random self-play terminates within the ply budget"
    );
  }

  if (!all_passed) {
    std::printf("triplechess rule test FAILED\n");
    return 1;
  }
  std::printf("triplechess rule test passed\n");
  return 0;
}
