from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Optional
from gods.models import Action_List, Card, Card_Id, Card_Type, Choice, Player, Game_State, effective_power


def draw_card(game: Game_State, player_id: int, agent: any, replacement_effects=True):
    """Draw a card from the player's deck."""
    player = game.players[player_id]
    if len(player.deck) == 0:
        return None

    if replacement_effects:
        for w in player.wonders:
            replaced = w.on_draw_replacement(game, agent)
            if replaced:
                return
    
    if len(player.deck) == 0:
        return
    
    for w in player.wonders:
        card_drawn = w.on_draw(game, agent)
        if card_drawn is not None:
            return card_drawn
        
    card = player.deck.pop()
    player.hand.append(card)
    return card


def discard_card(game: Game_State, card_id: Card_Id, agent: any):
    """Draw a card from the player's deck."""
    player_id = card_id.owner_index
    player = game.players[player_id]
    assert card_id.area == "hand"
    
    card = game.get_card(card_id)
    for w in player.wonders:
        w.on_discard(game, card, agent)
        
    del player.hand[card_id.card_index]
    player.discard.append(card)



def check_people_conditions(game: Game_State, ui: any) -> None:
    """Check and update ownership of people cards based on their conditions."""
    for people in game.peoples:
        old_owner = people.owner
        new_owner = evaluate_people_condition(game, people, ui)

        if new_owner != old_owner:
            # if new_owner is not None:
            #     print(f"{game.players[new_owner].name} now controls {people.name}!")
            # elif old_owner is not None:
            #     print(f"{people.name} is no longer controlled by anyone!")
            people.owner = new_owner


def evaluate_people_condition(game: Game_State, people: Card, ui: any) -> Optional[int]:
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


def play_card(state: Game_State, card_id: Card_Id, agent: any):
    """Play a card from the active player's hand. Accepts int index or Card_Id."""
    player = state.players[card_id.owner_index]
    card = state.get_card(card_id)
    if card_id.area == "hand":
        del player.hand[card_id.card_index]

    agent.message(f"{player.name} plays {card.name}")

    if card.card_type == Card_Type.WONDER:
        card.owner = state.current_player
        player.wonders.append(card)
    elif card.card_type == Card_Type.EVENT:
        player.discard.append(card)
    card.on_played(state, agent)

    # Check people conditions after playing
    check_people_conditions(state, agent)


def pass_turn(game: Game_State, ui: any) -> bool:
    """
    Active player passes and draws a card.
    Returns False if deck is empty (game ends).
    """
    player_id = game.current_player
    player = game.players[player_id]

    # Trigger "on pass" effects before drawing
    trigger_on_pass_effects(game, player, ui)

    if not player.deck:
        ui.message(f"{player.name}'s deck is empty! Game ends immediately!")
        game.game_over = True
        game.ending_player = game.current_player
        return False

    draw_card(game, player_id, ui)

    # Check people conditions after pass
    check_people_conditions(game, ui)

    # Advance to end phase
    game.current_phase = "end"

    return True


def trigger_on_pass_effects(game: Game_State, player: Player, agent: any) -> None:
    """Trigger effects that happen when a player passes."""
    for w in player.wonders:
        w.on_pass(game, agent)


def trigger_start_of_turn_effects(game: Game_State, agent: any) -> None:
    """Trigger effects at the start of a turn."""
    player = game.active_player()

    for w in player.wonders:
        w.on_turn_start(game, agent)


def trigger_end_of_turn_effects(game: Game_State, agent: any) -> None:
    """Trigger effects at the end of a turn."""
    player = game.active_player()

    for w in player.wonders:
        w.on_turn_end(game, agent)

def trigger_on_draw(game: Game_State, agent: any) -> None:
    player = game.active_player()
    for w in player.wonders:
        w.on_draw(game, agent)

def wonders_by_priority(state: Game_State) -> list[Card]:
    active_player = state.active_player()
    opponent = state.opponent()
    all_wonders = active_player.wonders + opponent.wonders
    return all_wonders

def destroy_people(game: Game_State, card_id: Card_Id, agent: any) -> None:
    people = game.get_card(card_id)
    # owner_idx = people.owner
    # if owner_idx is None or not is_indestructible(game, people, owner_idx):
    people.destroyed = True
    people.on_destroyed(game, agent)
    for card in wonders_by_priority(game):
        card.on_destroy(game, people, agent)

def destroy_wonder(game: Game_State, card_id: Card_Id, agent: any) -> None:
    card = game.get_card(card_id)
    assert card.card_type == Card_Type.WONDER, card.card_type
    owner_idx = card_id.owner_index
    if owner_idx is not None:
        player = game.players[owner_idx]
        player.wonders.remove(card)
        player.discard.append(card)

    card.on_destroyed(game, agent)
    for card in wonders_by_priority(game):
        card.on_destroy(game, card, agent)
    card.on_destroyed(game, agent)

def restore_people(game: Game_State, card_id: Card_Id, agent: any) -> None:
    people = game.get_card(card_id)
    people.destroyed = False
    # for card in wonders_by_priority(game):
        # card.on_restore(game, people, agent)

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

def declare_end_game(game: Game_State, ui: any) -> None:
    """Active player declares end of game."""
    # ui.message(f"{game.active_player().name} declares the end of the game!")
    game.game_ending = True
    game.ending_player = game.current_player
    # Advance to end phase
    game.current_phase = "end"


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


def calculate_scores(game: Game_State, ui: any) -> tuple[int, int]:
    """Calculate final scores for both players."""
    scores = [compute_player_score(game, 0), compute_player_score(game, 1)]
    ui.message(f"{game.players[0].name} scores {scores[0]} points")
    ui.message(f"{game.players[1].name} scores {scores[1]} points")
    return scores[0], scores[1]


# def determine_winner(game: Game_State, scores: tuple[int, int], ui: any) -> Optional[int]:
#     """
#     Determine the winner.
#     Returns 0 or 1 for player index, None for tie (shouldn't happen with tiebreaker).
#     """
#     if scores[0] > scores[1]:
#         return 0
#     elif scores[1] > scores[0]:
#         return 1
#     else:
#         # Tie - the player who triggered the end loses
#         if game.ending_player is not None:
#             return 1 - game.ending_player
#         return None



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
    def resolve(state: Game_State, choice: Choice, option_index: int, agent) -> None:
        card_id = Card_Id(area="hand", card_index=option_index, owner_index=state.current_player)
        play_card(state, card_id, agent)
    play_choice.resolve = resolve
    return play_choice

def perform_main_choice(state: Game_State, agent: any) -> Choice:
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

    def resolve(state: Game_State, choice: Choice, option_index: int, agent) -> None:
        action = choice.actions.actions[option_index]
        if action == "play":
            play_choice = make_play_choice(state)
            agent.perform_action(state, play_choice)
        elif action == "pass":
            pass_turn(state, agent)
        elif action == "end":
            declare_end_game(state, agent)
    choice.resolve = resolve

    agent.perform_action(state, choice)
    return choice

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

def game_loop(game: Game_State, agent: any, display = display_game_state) -> None:
    while not game.game_over:

        if game.current_phase == "start":
            # display_game_state(game)
            trigger_start_of_turn_effects(game, agent)
            game.current_phase = "main"
            continue
        if game.current_phase == "main":
            if display is not None:
                display(game)
            perform_main_choice(game, agent)
            game.current_phase = "end"
            continue
        if game.current_phase == "end":
            trigger_end_of_turn_effects(game, agent)
            game.switch_turn()
            game.current_phase = "start"
            continue
    
    if display is not None:
        display(game)
    agent.message("Game ended!")
    agent.message(f"Player 1: {compute_player_score(game, 0)}")
    agent.message(f"Player 2: {compute_player_score(game, 1)}")