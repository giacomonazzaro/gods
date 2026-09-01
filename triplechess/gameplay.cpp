#include "gameplay.h"

namespace triplechess {

static int  square_row(int square) { return square / BOARD_SIZE; }
static int  square_col(int square) { return square % BOARD_SIZE; }
static int  square_of(int row, int col) { return row * BOARD_SIZE + col; }
static bool on_board(int row, int col) {
  return row >= 0 && row < BOARD_SIZE && col >= 0 && col < BOARD_SIZE;
}

// The row a player starts on, and the row that player wins by reaching (the
// other player's home row).
static int home_row(int player) { return player == 0 ? 0 : BOARD_SIZE - 1; }
static int goal_row(int player) { return home_row(1 - player); }

static const int directions[8][2] = {
  {-1, -1}, {-1, 0}, {-1, 1}, {0, -1}, {0, 1}, {1, -1}, {1, 0}, {1, 1}
};

Move_List legal_moves(const Game_State& state) {
  Move_List moves;
  int       player = state.current_player;

  for (int row = 0; row < BOARD_SIZE; ++row) {
    for (int col = 0; col < BOARD_SIZE; ++col) {
      int value = state.board[row][col];
      if (piece_color(value) != player) continue;
      int type = piece_type(value);
      int from = square_of(row, col);

      for (const auto& direction : directions) {
        int to_row = row + direction[0];
        int to_col = col + direction[1];
        if (!on_board(to_row, to_col)) continue;
        int to     = square_of(to_row, to_col);
        int target = state.board[to_row][to_col];

        if (target == EMPTY) {
          moves.push_back(Move{from, to});
          continue;
        }
        if (piece_color(target) == player) continue;  // Own piece blocks.

        int target_type = piece_type(target);
        if (beats(type, target_type)) {
          moves.push_back(Move{from, to});
        } else if (target_type == type) {
          // A push off the edge of the board kills the pushed piece, so it is
          // always legal there; pushed onto the board, it needs the landing
          // square to be empty.
          int push_row = to_row + direction[0];
          int push_col = to_col + direction[1];
          if (!on_board(push_row, push_col) ||
              state.board[push_row][push_col] == EMPTY) {
            moves.push_back(Move{from, to});
          }
        }
        // Otherwise the enemy piece beats this one: no legal move there.
      }
    }
  }
  return moves;
}

void apply_move(Game_State& state, const Move& move) {
  int mover    = state.current_player;
  int from_row = square_row(move.from);
  int from_col = square_col(move.from);
  int to_row   = square_row(move.to);
  int to_col   = square_col(move.to);

  int moving_value = state.board[from_row][from_col];
  int target_value = state.board[to_row][to_col];

  // A push: the enemy piece on the destination square (same type as the
  // mover) hops one further square along the same direction, or is killed if
  // that square is off the board.
  if (target_value != EMPTY &&
      piece_type(target_value) == piece_type(moving_value)) {
    int push_row = to_row + (to_row - from_row);
    int push_col = to_col + (to_col - from_col);
    if (on_board(push_row, push_col)) {
      state.board[push_row][push_col] = target_value;
    }
  }

  state.board[to_row][to_col]     = moving_value;
  state.board[from_row][from_col] = EMPTY;

  // The mover wins by moving a piece onto the opponent's home row.
  if (to_row == goal_row(mover)) {
    state.winner    = mover;
    state.game_over = true;
    return;
  }

  state.switch_turn();
  if (legal_moves(state).empty()) {
    state.winner    = 2;  // No legal reply: a draw.
    state.game_over = true;
  }
}

int compute_player_score(const Game_State& state, int player) {
  return state.winner == player ? 1 : 0;
}

Game_State quick_setup(int seed) {
  Game_State game;
  game.init(seed);
  return game;
}

void Game_State::init(int /*seed*/) {
  *this = Game_State();

  static const int back_row[6] = {ROCK, PAPER, SCISSORS, ROCK, PAPER, SCISSORS};
  int              margin      = (BOARD_SIZE - 6) / 2;
  for (int i = 0; i < 6; ++i) {
    int col                    = margin + i;
    board[0][col]              = make_piece(back_row[i], 0);
    board[BOARD_SIZE - 1][col] = make_piece(back_row[i], 1);
  }
  begin_game();  // The opening decision to present.
}

// Write a UCI-style label for a move, e.g. "b2c3", into `out` (which must
// hold at least 5 chars: four coordinates, a null).
static void write_move_label(char* out, const Move& move) {
  int length    = 0;
  out[length++] = (char)('a' + square_col(move.from));
  out[length++] = (char)('1' + square_row(move.from));
  out[length++] = (char)('a' + square_col(move.to));
  out[length++] = (char)('1' + square_row(move.to));
  out[length]   = '\0';
}

Choice Game_State::next_choice() {
  if (game_over) return Choice{};

  Choice choice;
  choice.player_index     = current_player;
  choice.description      = "move";
  choice.text_description = "Move a piece";

  // Offer the legal moves; option index i corresponds to legal_moves()[i]. The
  // labels live in a thread-local buffer so the option targets can stay
  // non-owning const char*; it is safe under MCTS's threaded rollouts.
  choice.actions = [](Game& game) -> Choose {
    Game_State& state = static_cast<Game_State&>(game);
    Move_List   moves = legal_moves(state);

    static thread_local char labels[128][5];
    Choose_Option            option;
    for (int i = 0; i < moves.size(); ++i) {
      write_move_label(labels[i], moves[i]);
      option.targets.push_back(labels[i]);
    }
    return option;
  };

  // Apply the chosen move, then return the next decision.
  choice.resolve = [](Game& game, int index) -> Choice {
    Game_State& state = static_cast<Game_State&>(game);
    Move_List   moves = legal_moves(state);
    apply_move(state, moves[index]);
    return null_choice;
  };

  return choice;
}

}  // namespace triplechess
