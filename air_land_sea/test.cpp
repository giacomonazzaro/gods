// Rules checks for Air, Land, & Sea, plus a batch of random games.
//
//   compile air_land_sea air_land_sea_test

#include <air_land_sea/gameplay.h>
#include <game/agent.h>

#include <iostream>

using namespace air_land_sea;

static int failures = 0;

static void check(bool condition, const char* what) {
  if (condition) return;
  std::cerr << "FAILED: " << what << "\n";
  failures += 1;
}

// The index of a card, from the theater it belongs to and its strength.
static int card_of(Theater theater, int strength) {
  return theater * 6 + strength - 1;
}

// A battle with the theaters in a known order and nothing on the table.
static Game_State empty_battle() {
  auto state     = Game_State();
  state.theaters = {AIR, LAND, SEA};
  return state;
}

static void put(
  Game_State& state, int card, int position, int owner, bool face_down = false
) {
  state.board.push_back(Placement{
    (uint8_t)card, (uint8_t)position, (uint8_t)owner, (uint8_t)(face_down ? 1 : 0)
  });
}

// The options the pending choice offers, in the order it indexes them.
static Targets choice_targets(Game_State& state) {
  const Choose actions = pending_choice(state).actions(state);
  return std::get<Choose_Card>(actions).targets;
}

static bool contains(const Targets& targets, int target) {
  for (int offered : targets) {
    if (offered == target) return true;
  }
  return false;
}

static void test_strength() {
  auto state = empty_battle();
  put(state, card_of(AIR, 6), 0, 0);
  check(side_strength(state, 0, 0) == 6, "a face-up card counts its strength");

  put(state, card_of(LAND, 6), 1, 0, true);
  check(side_strength(state, 1, 0) == 2, "a face-down card counts 2");

  // Escalation is face up, so every face-down card of its owner counts 4.
  put(state, card_of(SEA, 2), 2, 0);
  check(side_strength(state, 1, 0) == 4, "Escalation makes face-down cards 4");

  // Support helps the theaters next to the one it is in, not its own.
  auto supported = empty_battle();
  put(supported, card_of(AIR, 1), 1, 0);
  check(side_strength(supported, 1, 0) == 1, "Support does not help its own");
  check(side_strength(supported, 0, 0) == 3, "Support helps the left theater");
  check(side_strength(supported, 2, 0) == 3, "Support helps the right theater");

  // Cover Fire makes the cards below it strength 4.
  auto covered = empty_battle();
  put(covered, card_of(AIR, 6), 0, 0);
  put(covered, card_of(LAND, 4), 0, 0);
  check(side_strength(covered, 0, 0) == 8, "Cover Fire makes covered cards 4");
}

static void test_control() {
  auto state         = empty_battle();
  state.first_player = 1;
  check(controls_theater(state, 0, 1), "the first player wins an empty theater");
  put(state, card_of(AIR, 6), 0, 0);
  check(controls_theater(state, 0, 0), "more strength takes the theater");
  check(theaters_controlled(state, 1) == 2, "the other two go to the first player");
}

static void test_deployment_rules() {
  auto state           = empty_battle();
  state.current_player = 0;
  state.hands[0].push_back((uint8_t)card_of(SEA, 6));

  // Column 0 is Air, so the Sea card can only go there face down.
  auto moves = turn_moves(state);
  bool face_up_in_air = false;
  for (int move : moves) {
    if (move == WITHDRAW_MOVE) continue;
    if (move_position(move) == 0 && !move_face_down(move)) face_up_in_air = true;
  }
  check(!face_up_in_air, "a card cannot be deployed to a non-matching theater");

  // Aerodrome opens non-matching theaters to cards of strength 3 or less.
  state.hands[0].push_back((uint8_t)card_of(SEA, 3));
  put(state, card_of(AIR, 4), 2, 0);
  moves                = turn_moves(state);
  bool small_in_air    = false;
  bool big_in_air      = false;
  for (int move : moves) {
    if (move == WITHDRAW_MOVE) continue;
    if (move_position(move) != 0 || move_face_down(move)) continue;
    if (move_card(move) == card_of(SEA, 3)) small_in_air = true;
    if (move_card(move) == card_of(SEA, 6)) big_in_air = true;
  }
  check(small_in_air, "Aerodrome lets a strength 3 card go anywhere");
  check(!big_in_air, "Aerodrome does not help a strength 6 card");
}

// "Uncovered" means no card of the same player was played on top of it in that
// theater. It says nothing about which way up the card is: a face-down card
// with nothing on it can be flipped face up, and a face-up card with something
// on it cannot be flipped at all.
static void test_uncovered_ignores_which_way_up() {
  auto state = empty_battle();
  put(state, card_of(AIR, 6), 0, 0, /*face_down=*/true);
  check(is_uncovered(state, card_of(AIR, 6)), "a lone face-down card is uncovered");

  put(state, card_of(AIR, 1), 0, 0);
  check(!is_uncovered(state, card_of(AIR, 6)), "a card played on top covers it");
  check(is_uncovered(state, card_of(AIR, 1)), "the card on top is uncovered");

  // The other player's cards in the same theater are their own pile.
  put(state, card_of(LAND, 6), 0, 1);
  check(is_uncovered(state, card_of(LAND, 6)),
        "the other player's cards do not cover yours");

  // Maneuver takes any uncovered card in the theaters next to it, either
  // player's and either way up.
  auto flipping = empty_battle();
  flipping.hands[0].push_back((uint8_t)card_of(AIR, 3));  // Maneuver.
  put(flipping, card_of(LAND, 6), 1, 1, /*face_down=*/true);
  put(flipping, card_of(SEA, 6), 1, 1);  // Played on top of it.
  put(flipping, card_of(LAND, 2), 1, 0, /*face_down=*/true);
  play_card(flipping, card_of(AIR, 3), 0, false, 0);
  flipping.begin_game();  // Takes Maneuver's choice off the queue.

  const auto offered = choice_targets(flipping);
  check(offered.size() == 2, "Maneuver offers every uncovered card next to it");
  check(!contains(offered, card_of(LAND, 6)), "a covered card is not offered");
  check(contains(offered, card_of(SEA, 6)), "a face-up uncovered card is offered");
  check(
    contains(offered, card_of(LAND, 2)), "a face-down uncovered card is offered"
  );
}

static void test_containment_and_blockade() {
  auto state = empty_battle();
  put(state, card_of(AIR, 5), 0, 1);  // Containment, the opponent's.
  play_card(state, card_of(LAND, 6), 1, true, 0);
  check(find_placement(state, card_of(LAND, 6)) == nullptr,
        "Containment destroys a card played face down");

  auto blocked = empty_battle();
  put(blocked, card_of(SEA, 5), 0, 0);  // Blockade in column 0.
  for (int i = 0; i < 3; ++i) put(blocked, card_of(LAND, i + 1), 1, 1);
  play_card(blocked, card_of(AIR, 6), 1, false, 0);
  check(find_placement(blocked, card_of(AIR, 6)) == nullptr,
        "Blockade destroys a card played into a full adjacent theater");
}

static void test_withdraw_points() {
  auto state = Game_State();
  state.init(7);
  state.hands[state.current_player].clear();
  state.hands[state.current_player].push_back(0);
  const int loser = state.current_player;
  resolve_choice(state, /*withdraw is the last move*/ turn_moves(state).size() - 1);
  check(state.points[1 - loser] == 4, "withdrawing with one card left scores 4");
}

// Plays whole games at random. Catches a rule that stops a game from ending
// and any state a choice cannot be answered in.
static void test_random_games() {
  auto agent = Agent_Random(12345);
  for (int game_index = 0; game_index < 200; ++game_index) {
    auto state = Game_State();
    state.init(game_index);

    int steps = 0;
    while (!state.is_game_over()) {
      const Choice& choice = pending_choice(state);
      check(!choice.is_null(), "a game that is not over has a choice");
      if (choice.is_null()) break;
      const int count = pending_action_count(state);
      check(count > 0, "a pending choice offers at least one option");
      if (count == 0) break;
      resolve_choice(state, agent.choose_action(state, choice));

      steps += 1;
      if (steps > 20000) {
        check(false, "a random game did not end");
        break;
      }
    }
    check(state.winner != -1, "a finished game has a winner");
    check(state.points[state.winner] >= POINTS_TO_WIN, "the winner reached 12");
  }
}

int main() {
  test_strength();
  test_control();
  test_uncovered_ignores_which_way_up();
  test_deployment_rules();
  test_containment_and_blockade();
  test_withdraw_points();
  test_random_games();

  if (failures == 0) {
    std::cout << "all checks passed\n";
    return 0;
  }
  std::cout << failures << " checks failed\n";
  return 1;
}
