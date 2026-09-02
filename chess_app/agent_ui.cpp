#include "agent_ui.h"

#include <chess/gameplay.h>

#include "ui.h"

int Chess_Agent_UI::choose_action(Game& game, const Choice&) {
  auto& state = static_cast<chess::Game_State&>(game);

  // Built once per turn: one Gesture_Drag_And_Drop per legal move, keyed by
  // the piece's Thing. A piece with several legal destinations gets several
  // gestures. The drop's container is the destination square, or the piece
  // standing there when the square is occupied (dragging over an occupied
  // square hovers that piece, not the square underneath it). Promotions
  // auto-queen, so the rook/bishop/knight options are skipped — otherwise
  // they would collide with the queen option on the same square.
  if (this->gesture_map.empty()) {
    chess::Move_List moves = chess::legal_moves(state);
    for (int i = 0; i < moves.size(); ++i) {
      const chess::Move& move = moves[i];
      if (move.promotion != 0 && move.promotion != chess::QUEEN) continue;
      int piece_id   = chess_piece_thing_on_square(move.from);
      int dest_thing = chess_piece_thing_on_square(move.to);
      int container   = dest_thing >= 0 ? dest_thing : move.to;
      this->gesture_map[piece_id].push_back(
        Gesture_Drag_And_Drop{container, i}
      );
    }
  }

  auto drag      = table.drag_state;
  auto drop      = table.poll_dropped_thing();
  int  action_id = this->process_gestures(drag, drop);
  if (action_id != -1) this->gesture_map.clear();
  return action_id;
}
