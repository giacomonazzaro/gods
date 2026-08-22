#include "gameplay.h"

namespace no_thanks {

int player_score(const Game_State& state, int player) {
  auto cards = std::vector<uint8_t>(
    state.taken[player].begin(), state.taken[player].end()
  );
  std::sort(cards.begin(), cards.end());

  int total = 0;
  for (size_t i = 0; i < cards.size(); ++i) {
    // A card that follows the one before it belongs to the same run, and only
    // the lowest card of a run counts.
    bool starts_a_run = i == 0 || cards[i] != cards[i - 1] + 1;
    if (starts_a_run) total += cards[i];
  }
  return total - state.chips[player];
}

int winning_player(const Game_State& state) {
  int winner = 0;
  for (int player = 1; player < PLAYER_COUNT; ++player) {
    if (player_score(state, player) < player_score(state, winner)) {
      winner = player;
    }
  }
  return winner;
}

void reveal_next_card(Game_State& state) {
  if (state.deck.empty()) {
    state.card_on_table = 0;
    state.game_over     = true;
    return;
  }
  state.card_on_table = state.deck.back();
  state.deck.pop_back();
  state.chips_on_card = 0;
}

void take_card(Game_State& state) {
  int player = state.current_player;
  state.taken[player].push_back(state.card_on_table);
  state.chips[player] += state.chips_on_card;
  state.chips_on_card = 0;
  // The player who took the card turns the next one over and decides again.
  reveal_next_card(state);
}

void pay_chip(Game_State& state) {
  state.chips[state.current_player] -= 1;
  state.chips_on_card += 1;
  state.current_player = (state.current_player + 1) % PLAYER_COUNT;
}

Game_State quick_setup(int seed) {
  Game_State game;
  game.init(seed);
  return game;
}

void Game_State::init(int seed) {
  *this    = Game_State();
  auto rng = std::mt19937((unsigned int)seed);

  auto cards = std::vector<uint8_t>();
  for (int value = LOWEST_CARD; value <= HIGHEST_CARD; ++value) {
    cards.push_back((uint8_t)value);
  }
  std::shuffle(cards.begin(), cards.end(), rng);
  // The nine cards past the deck's size are out of the game, and nobody sees
  // them.
  deck.assign(cards.begin(), cards.begin() + DECK_SIZE);

  current_player = (uint8_t)(rng() % PLAYER_COUNT);
  reveal_next_card(*this);
  begin_game();
}

Choice Game_State::next_choice() {
  if (game_over) return Choice{};

  Choice choice;
  choice.player_index     = current_player;
  choice.description      = "turn";
  choice.text_description = "Take the card, or pay a chip to pass it on";

  // A player with no chips left can only take the card.
  choice.actions = [](Game& game) -> Choose {
    static const char* labels[2] = {"Take", "No Thanks!"};
    Game_State&        state     = static_cast<Game_State&>(game);
    Choose_Option      option;
    option.targets.push_back(labels[TAKE_CARD]);
    if (state.chips[state.current_player] > 0) {
      option.targets.push_back(labels[PAY_CHIP]);
    }
    return option;
  };

  choice.resolve = [](Game& game, int index) -> Choice {
    Game_State& state = static_cast<Game_State&>(game);
    if (index == PAY_CHIP)
      pay_chip(state);
    else
      take_card(state);
    return null_choice;
  };

  return choice;
}

}  // namespace no_thanks
