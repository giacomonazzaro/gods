// Rules checks for No Thanks!, plus a batch of random games.
//
//   compile no_thanks no_thanks_test

#include <game/agent.h>
#include <no_thanks/gameplay.h>

#include <iostream>

using namespace no_thanks;

static int failures = 0;

static void check(bool condition, const char* what) {
  if (condition) return;
  std::cerr << "FAILED: " << what << "\n";
  failures += 1;
}

static void give(Game_State& state, int player, std::vector<int> cards) {
  for (int card : cards) state.taken[player].push_back((uint8_t)card);
}

static void test_scoring() {
  auto state = Game_State();
  state.chips.fill(0);

  give(state, 0, {5});
  check(player_score(state, 0) == 5, "a single card counts its number");

  give(state, 1, {7, 8, 9});
  check(player_score(state, 1) == 7, "a run counts only its lowest card");

  give(state, 2, {12, 14, 15, 20});
  check(player_score(state, 2) == 12 + 14 + 20, "two runs and a lone card");

  state.chips[0] = 3;
  check(player_score(state, 0) == 2, "each chip left counts -1");
}

// The searches maximize evaluate_state, so the player with the lower score
// must be the one it rates higher.
static void test_evaluate_prefers_a_low_score() {
  auto state = Game_State();
  state.chips.fill(0);
  give(state, 0, {10});
  give(state, 1, {25});
  give(state, 2, {25});
  check(
    evaluate_state(state, 0) > evaluate_state(state, 1),
    "the player with the lower score is rated higher"
  );
  check(evaluate_state(state, 0) > 1.0f, "being ahead rates above the middle");
  check(evaluate_state(state, 1) < 1.0f, "being behind rates below the middle");

  state.game_over = true;
  check(evaluate_state(state, 0) == 2.0f, "the lowest score wins the game");
  check(evaluate_state(state, 1) == 0.0f, "a higher score loses the game");
}

static void test_taking_and_paying() {
  auto state           = Game_State();
  state.card_on_table  = 20;
  state.current_player = 0;

  pay_chip(state);
  check(state.chips[0] == STARTING_CHIPS - 1, "paying costs a chip");
  check(state.chips_on_card == 1, "the chip lands on the card");
  check(state.current_player == 1, "the card passes to the next player");

  pay_chip(state);
  pay_chip(state);
  check(state.current_player == 0, "the card comes back around");
  check(state.chips_on_card == 3, "the chips pile up on the card");

  take_card(state);
  check(state.taken[0].size() == 1, "the card goes to the player who takes it");
  check(
    state.chips[0] == STARTING_CHIPS - 1 + 3, "the chips on it come along"
  );
  check(state.current_player == 0, "that player also plays the next card");
  check(state.game_over, "an empty deck ends the game");
}

static void test_a_player_with_no_chips_must_take() {
  auto state           = quick_setup(1);
  state.chips[state.current_player] = 0;
  state.begin_game();

  const Choice& choice  = pending_choice(state);
  Choose        actions = choice.actions(state);
  check(
    action_options_count(actions) == 1,
    "a player with no chips is offered only the card"
  );
}

// Every chip is either in front of a player or on the card, and every card of
// the deal ends up in front of someone.
static void test_random_games() {
  for (int seed = 0; seed < 200; ++seed) {
    auto state = quick_setup(seed);
    auto agent = Agent_Random(seed);

    int steps = 0;
    while (!state.is_game_over()) {
      const Choice& choice = pending_choice(state);
      if (pending_action_count(state) == 0) break;
      resolve_choice(state, agent.choose_action(state, choice));

      int chips = state.chips_on_card;
      for (int player = 0; player < PLAYER_COUNT; ++player) {
        chips += state.chips[player];
      }
      check(chips == PLAYER_COUNT * STARTING_CHIPS, "no chip is lost");

      steps += 1;
      if (steps > 20000) {
        check(false, "a random game did not end");
        break;
      }
    }

    int cards = 0;
    for (int player = 0; player < PLAYER_COUNT; ++player) {
      cards += state.taken[player].size();
    }
    check(cards == DECK_SIZE, "every card of the deal was taken");
    check(state.deck.empty(), "the deck is empty at the end");
  }
}

int main() {
  test_scoring();
  test_evaluate_prefers_a_low_score();
  test_taking_and_paying();
  test_a_player_with_no_chips_must_take();
  test_random_games();

  if (failures == 0) {
    std::cout << "all checks passed\n";
    return 0;
  }
  std::cout << failures << " checks failed\n";
  return 1;
}
