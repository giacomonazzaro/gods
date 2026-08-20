#include "gameplay.h"

namespace air_land_sea {

// The 18 cards, in index order: theater * 6 + strength - 1.
const Card_Design card_designs[CARD_COUNT] = {
  {"Support", "You gain +3 strength in each adjacent theater.", SUPPORT},
  {"Air Drop",
   "On your next turn you may play a card to a non-matching theater.",
   AIR_DROP},
  {"Maneuver", "Flip an uncovered card in an adjacent theater.", MANEUVER},
  {"Aerodrome",
   "You may play cards of strength 3 or less to non-matching theaters.",
   AERODROME},
  {"Containment",
   "If either player plays a card face down, destroy that card.",
   CONTAINMENT},
  {"Heavy Bombers", "", NO_ABILITY},

  {"Reinforce",
   "Look at the top card of the deck. You may play it face down to an "
   "adjacent theater.",
   REINFORCE},
  {"Ambush", "Flip an uncovered card in any theater.", AMBUSH},
  {"Maneuver", "Flip an uncovered card in an adjacent theater.", MANEUVER},
  {"Cover Fire", "All cards covered by this card are strength 4.", COVER_FIRE},
  {"Disrupt",
   "Your opponent flips one of their uncovered cards, then you flip one of "
   "yours.",
   DISRUPT},
  {"Heavy Tanks", "", NO_ABILITY},

  {"Transport", "You may move one of your cards to a different theater.",
   TRANSPORT},
  {"Escalation", "All of your face-down cards are strength 4.", ESCALATION},
  {"Maneuver", "Flip an uncovered card in an adjacent theater.", MANEUVER},
  {"Redeploy",
   "Return one of your face-down cards to your hand. If you do, take another "
   "turn.",
   REDEPLOY},
  {"Blockade",
   "If a card is played in an adjacent theater that already holds 3 or more "
   "cards, destroy that card.",
   BLOCKADE},
  {"Super Battleship", "", NO_ABILITY},
};

// ---- Queries ----

// True when a face-up Cover Fire of the same owner sits on top of this card.
static bool is_under_cover_fire(
  const Game_State& state, const Placement& placement
) {
  bool found = false;
  for (const Placement& other : state.board) {
    if (&other == &placement) {
      found = true;
      continue;
    }
    if (!found) continue;
    if (other.owner != placement.owner) continue;
    if (other.position != placement.position) continue;
    if (!other.face_down && ability_of(other.card) == COVER_FIRE) return true;
  }
  return false;
}

int strength_in_play(const Game_State& state, const Placement& placement) {
  if (is_under_cover_fire(state, placement)) return BOOSTED_STRENGTH;
  if (placement.face_down) {
    if (has_face_up(state, placement.owner, ESCALATION)) {
      return BOOSTED_STRENGTH;
    }
    return FACE_DOWN_STRENGTH;
  }
  return card_strength(placement.card);
}

int side_strength(const Game_State& state, int position, int player) {
  int strength = 0;
  for (const Placement& placement : state.board) {
    if (placement.owner != player) continue;
    // A face-up Support helps the theaters next to the one it is in.
    if (is_adjacent(placement.position, position) && !placement.face_down &&
        ability_of(placement.card) == SUPPORT) {
      strength += 3;
    }
    if (placement.position != position) continue;
    strength += strength_in_play(state, placement);
  }
  return strength;
}

bool controls_theater(const Game_State& state, int position, int player) {
  const int mine   = side_strength(state, position, player);
  const int theirs = side_strength(state, position, 1 - player);
  if (mine != theirs) return mine > theirs;
  return player == state.first_player;
}

int theaters_controlled(const Game_State& state, int player) {
  int count = 0;
  for (int position = 0; position < THEATER_COUNT; ++position) {
    if (controls_theater(state, position, player)) count += 1;
  }
  return count;
}

Targets turn_moves(const Game_State& state) {
  auto       moves     = Targets();
  const int  player    = state.current_player;
  const bool aerodrome = has_face_up(state, player, AERODROME);

  for (uint8_t card : state.hands[player]) {
    for (int position = 0; position < THEATER_COUNT; ++position) {
      const bool matching = state.theaters[position] == card_theater(card);
      const bool aerodrome_allows = aerodrome && card_strength(card) <= 3;
      if (matching || state.air_drop[player] || aerodrome_allows) {
        moves.push_back(pack_move(card, position, false));
      }
      moves.push_back(pack_move(card, position, true));
    }
  }
  moves.push_back(WITHDRAW_MOVE);
  return moves;
}

int compute_player_score(const Game_State& state, int player) {
  return state.points[player];
}

// ---- Choice helpers ----

Choice make_choice(
  int                                   player,
  const char*                           description,
  std::function<Targets(Game_State&)>   get_targets,
  std::function<void(Game_State&, int)> on_chosen
) {
  auto choice             = Choice();
  choice.player_index     = player;
  choice.description      = description;
  choice.text_description = description;
  choice.actions          = [get_targets](Game& game) -> Choose {
    return Choose_Card{get_targets(static_cast<Game_State&>(game)), false};
  };
  choice.resolve = [get_targets, on_chosen](Game& game, int index) -> Choice {
    Game_State& state = static_cast<Game_State&>(game);
    on_chosen(state, get_targets(state)[index]);
    return null_choice;
  };
  return choice;
}

// ---- Abilities ----

// Uncovered cards in the columns next to the one `card` sits in. Empty when
// the card left the table before its ability resolved.
static Targets adjacent_flip_targets(Game_State& state, int card) {
  auto             targets   = Targets();
  const Placement* placement = find_placement(state, card);
  if (!placement) return targets;
  for (const Placement& other : state.board) {
    if (!is_adjacent(other.position, placement->position)) continue;
    if (!is_uncovered(state, other.card)) continue;
    targets.push_back(other.card);
  }
  return targets;
}

static Targets any_flip_targets(Game_State& state) {
  auto targets = Targets();
  for (const Placement& placement : state.board) {
    if (!is_uncovered(state, placement.card)) continue;
    targets.push_back(placement.card);
  }
  return targets;
}

static Targets own_flip_targets(Game_State& state, int player) {
  auto targets = Targets();
  for (const Placement& placement : state.board) {
    if (placement.owner != player) continue;
    if (!is_uncovered(state, placement.card)) continue;
    targets.push_back(placement.card);
  }
  return targets;
}

// Columns next to the one `card` sits in, where Reinforce may play the top
// card of the deck.
static Targets reinforce_targets(Game_State& state, int card) {
  auto             targets   = Targets();
  const Placement* placement = find_placement(state, card);
  if (!placement || state.deck.empty()) return targets;
  for (int position = 0; position < THEATER_COUNT; ++position) {
    if (!is_adjacent(position, placement->position)) continue;
    targets.push_back(position);
  }
  if (!targets.empty()) targets.push_back(DECLINE);
  return targets;
}

static Targets transport_targets(Game_State& state, int player) {
  auto targets = Targets();
  for (const Placement& placement : state.board) {
    if (placement.owner != player) continue;
    for (int position = 0; position < THEATER_COUNT; ++position) {
      if (position == placement.position) continue;
      targets.push_back(pack_transport(placement.card, position));
    }
  }
  if (!targets.empty()) targets.push_back(DECLINE);
  return targets;
}

static Targets redeploy_targets(Game_State& state, int player) {
  auto targets = Targets();
  for (const Placement& placement : state.board) {
    if (placement.owner != player || !placement.face_down) continue;
    targets.push_back(placement.card);
  }
  if (!targets.empty()) targets.push_back(DECLINE);
  return targets;
}

static void take_off_board(Game_State& state, int card) {
  for (int i = 0; i < state.board.size(); ++i) {
    if (state.board[i].card != card) continue;
    state.board.erase(state.board.begin() + i);
    return;
  }
}

void destroy_card(Game_State& state, int card) {
  take_off_board(state, card);
  state.deck.push_back((uint8_t)card);
}

static void use_ability(Game_State& state, int card, int player) {
  const int opponent = 1 - player;
  switch (ability_of(card)) {
    case AIR_DROP: state.air_drop[player] = 1; break;

    case MANEUVER:
      state.queue.push_back(make_choice(
        player,
        "maneuver",
        [card](Game_State& state) { return adjacent_flip_targets(state, card); },
        [](Game_State& state, int target) { flip_card(state, target); }
      ));
      break;

    case AMBUSH:
      state.queue.push_back(make_choice(
        player,
        "ambush",
        [](Game_State& state) { return any_flip_targets(state); },
        [](Game_State& state, int target) { flip_card(state, target); }
      ));
      break;

    case DISRUPT:
      // The opponent picks first, then the player who played Disrupt.
      state.queue.push_back(make_choice(
        opponent,
        "disrupt",
        [opponent](Game_State& state) {
          return own_flip_targets(state, opponent);
        },
        [](Game_State& state, int target) { flip_card(state, target); }
      ));
      state.queue.push_back(make_choice(
        player,
        "disrupt",
        [player](Game_State& state) { return own_flip_targets(state, player); },
        [](Game_State& state, int target) { flip_card(state, target); }
      ));
      break;

    case REINFORCE:
      state.queue.push_back(make_choice(
        player,
        "reinforce",
        [card](Game_State& state) { return reinforce_targets(state, card); },
        [player](Game_State& state, int target) {
          if (target == DECLINE) return;
          const int top = state.deck.front();
          state.deck.erase(state.deck.begin());
          play_card(state, top, target, true, player);
        }
      ));
      break;

    case TRANSPORT:
      state.queue.push_back(make_choice(
        player,
        "transport",
        [player](Game_State& state) { return transport_targets(state, player); },
        [](Game_State& state, int target) {
          if (target == DECLINE) return;
          const int  moved     = transport_card(target);
          Placement* placement = find_placement(state, moved);
          if (!placement) return;
          // A moved card goes on top of whatever is already there, so it
          // leaves the board and joins it again at the end.
          auto copy     = *placement;
          copy.position = (uint8_t)transport_position(target);
          take_off_board(state, moved);
          state.board.push_back(copy);
        }
      ));
      break;

    case REDEPLOY:
      state.queue.push_back(make_choice(
        player,
        "redeploy",
        [player](Game_State& state) { return redeploy_targets(state, player); },
        [player](Game_State& state, int target) {
          if (target == DECLINE) return;
          take_off_board(state, target);
          state.hands[player].push_back((uint8_t)target);
          state.extra_turn = true;
        }
      ));
      break;

    default: break;  // An ongoing ability owes nobody a decision.
  }
}

// True when a face-up Blockade sits in a column next to this one.
static bool blockade_watches(const Game_State& state, int position) {
  for (const Placement& placement : state.board) {
    if (placement.face_down) continue;
    if (ability_of(placement.card) != BLOCKADE) continue;
    if (is_adjacent(placement.position, position)) return true;
  }
  return false;
}

void play_card(
  Game_State& state, int card, int position, bool face_down, int player
) {
  const int cards_before = cards_in_theater(state, position);
  state.board.push_back(Placement{
    (uint8_t)card, (uint8_t)position, (uint8_t)player, (uint8_t)(face_down ? 1 : 0)
  });

  const bool containment = has_face_up(state, 0, CONTAINMENT) ||
                           has_face_up(state, 1, CONTAINMENT);
  if (face_down && containment) {
    destroy_card(state, card);
    return;
  }
  if (cards_before >= 3 && blockade_watches(state, position)) {
    destroy_card(state, card);
    return;
  }
  if (!face_down) use_ability(state, card, player);
}

void flip_card(Game_State& state, int card) {
  Placement* placement = find_placement(state, card);
  if (!placement) return;
  placement->face_down = !placement->face_down;
  if (placement->face_down) return;
  use_ability(state, card, placement->owner);
}

// ---- Battles ----

void deal_battle(Game_State& state) {
  state.board.clear();
  state.deck.clear();
  state.hands[0].clear();
  state.hands[1].clear();
  state.withdrew   = -1;
  state.turn_taken = false;
  state.extra_turn = false;
  state.air_drop   = {0, 0};

  auto cards = std::vector<uint8_t>(CARD_COUNT);
  for (int i = 0; i < CARD_COUNT; ++i) cards[i] = (uint8_t)i;
  auto rng = std::mt19937(state.random_seed);
  std::shuffle(cards.begin(), cards.end(), rng);
  state.random_seed = (unsigned int)rng();

  int next = 0;
  for (int player = 0; player < 2; ++player) {
    for (int i = 0; i < HAND_SIZE; ++i) {
      state.hands[player].push_back(cards[next++]);
    }
  }
  while (next < CARD_COUNT) state.deck.push_back(cards[next++]);

  state.current_player = state.first_player;
}

// The battle is decided, so hand out the points and set up what comes next.
static void score_battle(Game_State& state) {
  int winner = 0;
  int points = 0;
  if (state.withdrew != -1) {
    winner = 1 - state.withdrew;
    // The longer the loser waited, the more the winner scores.
    const int left = state.hands[state.withdrew].size();
    points         = left >= 4 ? 2 : left >= 2 ? 3 : left == 1 ? 4 : 5;
  } else {
    winner = theaters_controlled(state, 0) >= 2 ? 0 : 1;
    points = 6;
  }

  state.points[winner] += points;
  if (state.points[winner] >= POINTS_TO_WIN) {
    state.game_over = true;
    state.winner    = winner;
    state.queue.clear();
    return;
  }

  // The theaters rotate one place to the right and the first-player card goes
  // to the other player.
  const auto theaters = state.theaters;
  state.theaters      = {theaters[2], theaters[0], theaters[1]};
  state.first_player  = 1 - state.first_player;
  deal_battle(state);
}

static bool battle_is_over(const Game_State& state) {
  if (state.withdrew != -1) return true;
  return state.hands[0].empty() && state.hands[1].empty();
}

static Choice make_turn_choice(Game_State& state) {
  const int player = state.current_player;
  return make_choice(
    player,
    "turn",
    [](Game_State& state) { return turn_moves(state); },
    [player](Game_State& state, int move) {
      state.turn_taken = true;
      if (move == WITHDRAW_MOVE) {
        state.withdrew = (int8_t)player;
        return;
      }
      const int card = move_card(move);
      for (int i = 0; i < state.hands[player].size(); ++i) {
        if (state.hands[player][i] != card) continue;
        state.hands[player].erase(state.hands[player].begin() + i);
        break;
      }
      // Air Drop arms the next card its player takes out of hand, and playing
      // that card uses it up.
      if (ability_of(card) != AIR_DROP) state.air_drop[player] = 0;
      play_card(state, card, move_position(move), move_face_down(move), player);
    }
  );
}

static bool has_targets(const Choose& choose) {
  return std::visit(
    [](const auto& option) { return option.targets.size() > 0; }, choose
  );
}

Choice Game_State::next_choice() {
  Game_State& state = *this;
  while (!state.game_over) {
    // Abilities that owe a decision come first. One whose targets have all
    // gone in the meantime is dropped.
    if (!state.queue.empty()) {
      auto choice = state.queue.front();
      state.queue.erase(state.queue.begin());
      if (has_targets(choice.actions(state))) return choice;
      continue;
    }

    // The turn only passes once the abilities it started are done.
    if (state.turn_taken) {
      state.turn_taken = false;
      if (state.extra_turn) {
        state.extra_turn = false;
      } else {
        state.current_player = 1 - state.current_player;
      }
      continue;
    }

    if (battle_is_over(state)) {
      score_battle(state);
      continue;
    }

    // A hand runs empty one turn before the other only if an ability took a
    // card out of turn order; the player with cards left carries on.
    if (state.hands[state.current_player].empty()) {
      state.current_player = 1 - state.current_player;
      continue;
    }
    return make_turn_choice(state);
  }
  return null_choice;
}

// ---- Setup ----

void Game_State::init(int seed) {
  // A deal starts from an empty game, whatever was played here before.
  *this = Game_State();

  auto rng = std::mt19937((unsigned int)seed);
  // The three theaters go in a row in a random order.
  auto order = std::vector<uint8_t>{AIR, LAND, SEA};
  std::shuffle(order.begin(), order.end(), rng);
  theaters = {order[0], order[1], order[2]};

  first_player = (uint8_t)(rng() % 2);
  random_seed  = (unsigned int)rng();
  deal_battle(*this);
  begin_game();
}

}  // namespace air_land_sea
