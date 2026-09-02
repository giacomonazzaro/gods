#include "agent_ui.h"

#include <triplechess/gameplay.h>

#include "ui.h"

int Triplechess_Agent_UI::choose_action(Game& game, const Choice&) {
  auto& state = static_cast<triplechess::Game_State&>(game);

  // Built once per turn: one Gesture_Drag_And_Drop per legal move, keyed by
  // the piece's Thing. A piece with several legal destinations gets several
  // gestures. The drop's container is the destination square, or the piece
  // standing there when the square is occupied (dragging over an occupied
  // square hovers that piece, not the square underneath it).
  if (this->gesture_map.empty()) {
    triplechess::Move_List moves = triplechess::legal_moves(state);
    for (int i = 0; i < moves.size(); ++i) {
      const triplechess::Move& move      = moves[i];
      int piece_id                       = triplechess_piece_thing_on_square(move.from);
      int dest_thing                     = triplechess_piece_thing_on_square(move.to);
      int container                      = dest_thing >= 0 ? dest_thing : move.to;
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
