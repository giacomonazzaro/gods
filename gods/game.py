from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Optional
from gods.models import Action_List, Card, Card_Id, Card_Type, Choice, Player, Game_State, effective_power


def draw_card(game: Game_State, player_id: int, replacement_effects=True):
    """Draw a card from the player's deck."""
    player = game.players[player_id]
    if len(player.deck) == 0:
        return None

    if replacement_effects:
        for w in player.wonders:
            choice = w.on_draw_replacement(game)
            if choice:
                game.choices.append(choice)
                return

    if len(player.deck) == 0:
        return

    for w in player.wonders:
        choice = w.on_draw(game)
        if choice is not None:
            game.choices.append(choice)
            return

    card = player.deck.pop()
    player.hand.append(card)
    return card


def discard_card(game: Game_State, card_id: Card_Id):
    """Discard a card from a player's hand."""
    player_id = card_id.owner_index
    player = game.players[player_id]
    assert card_id.area == "hand"

    card = game.get_card(card_id)
    for w in player.wonders:
        w.on_discard(game, card)

    del player.hand[card_id.card_index]
    player.discard.append(card)



def check_people_conditions(game: Game_State) -> None:
    """Check and update ownership of people cards based on their conditions."""
    for people in game.peoples:
        old_owner = people.owner
        new_owner = evaluate_people_condition(game, people)

        if new_owner != old_owner:
            people.owner = new_owner


def evaluate_people_condition(game: Game_State, people: Card) -> Optional[int]:
    """
    Evaluate who should control a people card.
    Returns player index (0 or 1) or None if tied/no one qualifies.
    """
    scores = [
        people.eval_points(game, 0),
        people.eval_points(game, 1)
    ]

    if scores[0] > scores[1] and scores[0] > 0:
        return 0
    elif scores[1] > scores[0] and scores[1] > 0:
        return 1
    else:
        # Tie or no one qualifies - check for wonders that break ties
        if scores[0] == scores[1] and scores[0] > 0:
            for i, player in enumerate(game.players):
                for w in player.wonders:
                    if w.wins_tie(game, people):
                        return i
        return None


def play_card(state: Game_State, card_id: Card_Id):
    """Play a card from a player's hand."""
    player = state.players[card_id.owner_index]
    card = state.get_card(card_id)
    if card_id.area == "hand":
        del player.hand[card_id.card_index]

    if card.card_type == Card_Type.WONDER:
        card.owner = state.current_player
        player.wonders.append(card)
    elif card.card_type == Card_Type.EVENT:
        player.discard.append(card)
    choice = card.on_played(state)
    if choice is not None:
        state.choices.append(choice)


def wonders_by_priority(state: Game_State) -> list[Card]:
    active_player = state.active_player()
    opponent = state.opponent()
    all_wonders = active_player.wonders + opponent.wonders
    return all_wonders

def destroy_people(game: Game_State, card_id: Card_Id) -> None:
    people = game.get_card(card_id)
    people.destroyed = True
    people.on_destroyed(game)
    for card in wonders_by_priority(game):
        card.on_destroy(game, people)

def destroy_wonder(game: Game_State, card_id: Card_Id) -> None:
    card = game.get_card(card_id)
    assert card.card_type == Card_Type.WONDER, card.card_type
    owner_idx = card_id.owner_index
    if owner_idx is not None:
        player = game.players[owner_idx]
        player.wonders.remove(card)
        player.discard.append(card)

    card.on_destroyed(game)
    for w in wonders_by_priority(game):
        w.on_destroy(game, card)

def restore_people(game: Game_State, card_id: Card_Id) -> None:
    people = game.get_card(card_id)
    people.destroyed = False

def shuffle_wonder_into_deck(game: Game_State, card_id: Card_Id) -> None:
    card = game.get_card(card_id)
    assert card.card_type == Card_Type.WONDER, card.card_type
    assert card_id.area in ["wonders", "discard"], f"{card_id.area}"
    assert card_id.owner_index is not None
    owner_idx = card_id.owner_index
    if owner_idx is not None:
        player = game.players[owner_idx]
        player.wonders.remove(card)
        card.counters = 0
        player.deck.append(card)
        random.shuffle(player.deck)

def declare_end_game(game: Game_State) -> None:
    """Active player declares end of game."""
    game.game_ending = True
    game.ending_player = game.current_player


def compute_player_score(game: Game_State, player_index: int) -> int:
    """Compute the total score for a player."""
    score = 0
    player = game.players[player_index]

    # Points from peoples where this player meets the condition
    for people in game.peoples:
        points = people.eval_points(game, player_index)
        if people.destroyed:
            points = 0
        for wonder in player.wonders:
            points = wonder.on_scoring_people(game, people, points)
        score += points

    # Points from wonders (Animals, Love)
    for wonder in player.wonders:
        score += wonder.on_scoring(game)

    return score


def make_play_choice(state: Game_State) -> Choice:
    play_choice = Choice()
    play_choice.player_index = state.current_player
    selection = []
    for i, card in enumerate(state.players[state.current_player].hand):
        card_id = Card_Id(area="hand", card_index=i, owner_index=state.current_player)
        selection.append(card_id)
    play_choice.actions = Action_List(
        type="choose-card",
        actions=selection
    )
    def resolve(state: Game_State, choice: Choice, option_index: int) -> None:
        card_id = Card_Id(area="hand", card_index=option_index, owner_index=state.current_player)
        play_card(state, card_id)
        state.current_phase = "post-play"
    play_choice.resolve = resolve
    return play_choice

def make_main_choice(state: Game_State) -> Choice:
    choice = Choice()
    choice.player_index = state.current_player
    player = state.active_player()

    # Build options based on what's available
    options = []
    if player.hand:
        options.append("play")
    options.append("pass")
    options.append("end")

    choice.actions = Action_List(
        type="main",
        actions=options
    )

    def resolve(state: Game_State, choice: Choice, option_index: int) -> None:
        action = choice.actions.actions[option_index]
        if action == "play":
            play_choice = make_play_choice(state)
            state.choices.append(play_choice)
        elif action == "pass":
            # Push on_pass choices, then set phase for draw
            player = state.active_player()
            for w in player.wonders:
                c = w.on_pass(state)
                if c is not None:
                    state.choices.append(c)
            state.current_phase = "post-pass-effects"
        elif action == "end":
            declare_end_game(state)
            state.current_phase = "end"
    choice.resolve = resolve
    return choice


def get_next_choice(state: Game_State) -> Choice:
    """Advance game state until a choice is produced or the game ends."""
    while not state.game_over:
        if state.choices:
            choice = state.choices.pop(0)
            if choice.generate_actions:
                choice.generate_actions(state, choice)
            if not choice.actions or not choice.actions.actions:
                continue
            return choice

        if state.current_phase == "start":
            for w in state.active_player().wonders:
                c = w.on_turn_start(state)
                if c:
                    state.choices.append(c)
            
            state.current_phase = "main"

        elif state.current_phase == "main":
            state.choices.append(make_main_choice(state))

        elif state.current_phase == "post-play":
            check_people_conditions(state)
            state.current_phase = "end"

        elif state.current_phase == "post-pass-effects":
            # on_pass choices already resolved, now draw
            player = state.active_player()
            if not player.deck:
                state.game_over = True
                state.ending_player = state.current_player
                continue
            draw_card(state, state.current_player)
            check_people_conditions(state)
            state.current_phase = "post-pass-draw"

        elif state.current_phase == "post-pass-draw":
            # draw choices resolved
            check_people_conditions(state)
            state.current_phase = "end"

        elif state.current_phase == "end":
            for w in state.active_player().wonders:
                c = w.on_turn_end(state)
                if c:
                    state.choices.append(c)
            state.switch_turn()
            state.current_phase = "start"

    return None


def detailed_str(card: Card) -> str:
    counters_str = f" (+{card.counters})" if card.counters > 0 else (f" ({card.counters})" if card.counters < 0 else "")
    return f"{card.name} [{card.color.value} {card.card_type.value}, power {card.power}{counters_str}] - {card.effect}"

def display_game_state(game: Game_State, current_player_view: bool = True) -> None:
    """Display the current game state."""
    print("\n" + "=" * 60)
    print("GAME STATE")
    print("=" * 60)

    # People cards
    print("\n--- PEOPLE CARDS (Center) ---")
    for people in game.peoples:
        owner_str = f" - Controlled by {game.players[people.owner].name}" if people.owner is not None else " - Unclaimed"
        status_str = " [DESTROYED]" if people.destroyed else ""
        effect_text = people.effect
        print(f"  {people}{status_str}{owner_str}")
        print(f"    Effect: {effect_text}")

    # Both players' info
    for i, player in enumerate(game.players):
        is_current = (i == game.current_player)
        marker = " <<< CURRENT TURN" if is_current else ""
        print(f"\n--- {player.name}{marker} ---")
        print(f"  Deck: {len(player.deck)} cards | Discard: {len(player.discard)} cards")

        if player.wonders:
            print(f"  Wonders in play:")
            for w in player.wonders:
                print(f"    - {detailed_str(w)}")
        else:
            print(f"  Wonders in play: None")

        # Show hand for current player (or both in hot-seat mode)
        print(f"  Hand ({len(player.hand)} cards):")
        for card in player.hand:
            print(f"    - {detailed_str(card)}")
        print("  points:", compute_player_score(game, i))
    print("\n" + "=" * 60)

def game_loop(game: Game_State, agent: any, display = display_game_state):
    while not game.game_over:
        choice = get_next_choice(game)
        if choice is None:
            break
        if display is not None and choice.actions.type == "main":
            display(game)
        index = agent.choose_action(game, choice)
        choice.resolve(game, choice, index)

    if display is not None:
        display(game)
    print("Game ended!")
    print(f"Player 1: {compute_player_score(game, 0)}")
    print(f"Player 2: {compute_player_score(game, 1)}")
