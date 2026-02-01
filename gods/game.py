from __future__ import annotations
import random
import copy
from typing import Optional
from gods.models import Card, Card_Type, Card_Color, Player, Game_State
from gods.cards import (
    get_people_cards, execute_card_effect, draw_card,
    get_wonder_power_bonus, get_event_power_bonus, get_event_power_penalty
)


def create_game(player1_deck: list[Card], player2_deck: list[Card], people_cards: list[Card]) -> Game_State:
    """Initialize a new game with the given decks and people cards."""
    p1 = Player(name="Player 1", deck=player1_deck.copy())
    p2 = Player(name="Player 2", deck=player2_deck.copy())

    random.shuffle(p1.deck)
    random.shuffle(p2.deck)

    game = Game_State(
        players=[p1, p2],
        peoples=people_cards.copy()
    )

    return game


def setup_game(game: Game_State, ui: any) -> None:
    """Draw initial hands for both players."""
    for player in game.players:
        for _ in range(5):
            if player.deck:
                card = player.deck.pop()
                player.hand.append(card)


def check_people_conditions(game: Game_State, ui: any) -> None:
    """Check and update ownership of people cards based on their conditions."""
    for people in game.peoples:
        old_owner = people.owner
        new_owner = evaluate_people_condition(game, people, ui)

        if new_owner != old_owner:
            if new_owner is not None:
                ui.message(f"{game.players[new_owner].name} now controls {people.name}!")
            elif old_owner is not None:
                ui.message(f"{people.name} is no longer controlled by anyone!")
            people.owner = new_owner


def evaluate_people_condition(game: Game_State, people: Card, ui: any) -> Optional[int]:
    """
    Evaluate who should control a people card.
    Returns player index (0 or 1) or None if tied/no one qualifies.
    """
    scores = [0, 0]

    if people.name == "Egyptians":
        # You have the most total power among green wonders
        for i, player in enumerate(game.players):
            scores[i] = sum(
                w.effective_power() + get_wonder_power_bonus(game, i, w)
                for w in player.wonders if w.color == Card_Color.GREEN
            )

    elif people.name == "Greeks":
        # You have twice or more cards in hand than the opponent
        for i, player in enumerate(game.players):
            opponent = game.players[1 - i]
            if len(player.hand) >= 2 * len(opponent.hand) and len(opponent.hand) > 0:
                scores[i] = 1
            elif len(player.hand) >= 2 and len(opponent.hand) == 0:
                scores[i] = 1

    elif people.name == "Vikings":
        # You have the most cards in your deck
        for i, player in enumerate(game.players):
            scores[i] = len(player.deck)

    elif people.name == "Minoans":
        # You have the most wonders
        for i, player in enumerate(game.players):
            scores[i] = len(player.wonders)

    elif people.name == "Babylonians":
        # You have the most total power among wonders
        for i, player in enumerate(game.players):
            scores[i] = sum(
                w.effective_power() + get_wonder_power_bonus(game, i, w)
                for w in player.wonders
            )

    elif people.name == "Romans":
        # You have the most total power among red wonders
        for i, player in enumerate(game.players):
            scores[i] = sum(
                w.effective_power() + get_wonder_power_bonus(game, i, w)
                for w in player.wonders if w.color == Card_Color.RED
            )

    elif people.name == "Judeans":
        # You have the most total power among blue wonders
        for i, player in enumerate(game.players):
            scores[i] = sum(
                w.effective_power() + get_wonder_power_bonus(game, i, w)
                for w in player.wonders if w.color == Card_Color.BLUE
            )

    # Determine winner
    if scores[0] > scores[1] and scores[0] > 0:
        return 0
    elif scores[1] > scores[0] and scores[1] > 0:
        return 1
    else:
        # Tie or no one qualifies - check Rivers wonder for tie-breaking
        if scores[0] == scores[1] and scores[0] > 0:
            for i, player in enumerate(game.players):
                for w in player.wonders:
                    if w.name == "Rivers" and people.effective_power() <= w.effective_power():
                        return i
        return None


def play_card(game: Game_State, card: Card, ui: any) -> bool:
    """Play a card from the active player's hand."""
    player = game.active_player()

    if card not in player.hand:
        ui.message("Card not in hand!")
        return False

    player.hand.remove(card)

    # Apply power bonuses/penalties for events
    original_counters = card.counters
    if card.card_type == Card_Type.EVENT:
        bonus = get_event_power_bonus(game, game.current_player, card)
        penalty = get_event_power_penalty(game, game.current_player, card)
        net = bonus - penalty
        # Minimum power of 1 when Sky is in effect
        if penalty > 0:
            effective = max(1, card.power + card.counters + net)
            card.counters = effective - card.power
        else:
            card.counters += net

    ui.message(f"{player.name} plays {card.detailed_str()}")

    # Execute effect
    execute_card_effect(game, card, ui)

    # Reset counters for events
    card.counters = original_counters

    if card.card_type == Card_Type.WONDER:
        player.wonders.append(card)
        # Trigger Moon effect (draw up to ○ cards)
        trigger_moon_effect(game, player, ui)
    elif card.card_type == Card_Type.EVENT:
        player.discard.append(card)

    # Check people conditions after playing
    check_people_conditions(game, ui)

    return True


def pass_turn(game: Game_State, ui: any) -> bool:
    """
    Active player passes and draws a card.
    Returns False if deck is empty (game ends).
    """
    player = game.active_player()

    # Trigger "on pass" effects before drawing
    trigger_on_pass_effects(game, player, ui)

    if not player.deck:
        ui.message(f"{player.name}'s deck is empty! Game ends immediately!")
        game.game_over = True
        game.ending_player = game.current_player
        return False

    draw_card(game, player, ui)

    # Check Moon effect after drawing
    trigger_moon_effect(game, player, ui)

    # Check people conditions after pass
    check_people_conditions(game, ui)

    return True


def trigger_on_pass_effects(game: Game_State, player: Player, ui: any) -> None:
    """Trigger effects that happen when a player passes."""
    player_idx = game.players.index(player)

    for w in player.wonders:
        # Knowledge: When you pass, you may play a card with power ○ or less
        if w.name == "Knowledge":
            power = w.effective_power()
            playable = [c for c in player.hand if c.power <= power and c.card_type != Card_Type.PEOPLE]
            if playable:
                choice = ui.ask_yes_no(f"Knowledge: Play a card with power {power} or less?")
                if choice:
                    selected = ui.select_card(f"Select a card to play (power {power} or less):", playable)
                    if selected:
                        play_card(game, selected, ui)

        # Forests: When you pass, you may restore a people with power ○ or less
        if w.name == "Forests":
            power = w.effective_power()
            destroyed = [p for p in game.peoples if p.destroyed and p.effective_power() <= power]
            if destroyed:
                choice = ui.ask_yes_no(f"Forests: Restore a people with power {power} or less?")
                if choice:
                    selected = ui.select_card("Select a people to restore:", destroyed)
                    if selected:
                        selected.destroyed = False
                        ui.message(f"{selected.name} was restored by Forests!")

        # War: When you pass, you may destroy a people with power ○ or less
        if w.name == "War":
            power = w.effective_power()
            from cards import is_indestructible
            targets = [p for p in game.peoples
                      if not p.destroyed and p.effective_power() <= power
                      and (p.owner is None or not is_indestructible(game, p, p.owner))]
            if targets:
                choice = ui.ask_yes_no(f"War: Destroy a people with power {power} or less?")
                if choice:
                    selected = ui.select_card("Select a people to destroy:", targets)
                    if selected:
                        selected.destroyed = True
                        ui.message(f"{selected.name} was destroyed by War!")


def trigger_moon_effect(game: Game_State, player: Player, ui: any) -> None:
    """Trigger Moon wonder effect - draw back to ○ cards if below."""
    for w in player.wonders:
        if w.name == "Moon":
            threshold = w.effective_power()
            while len(player.hand) < threshold and player.deck:
                card = player.deck.pop()
                player.hand.append(card)
                ui.message(f"Moon: {player.name} drew {card.name}.")


def trigger_start_of_turn_effects(game: Game_State, ui: any) -> None:
    """Trigger effects at the start of a turn."""
    player = game.active_player()

    for w in player.wonders:
        # Light: At the start of your turn, you may play a card with power ○ or less
        if w.name == "Light":
            power = w.effective_power()
            playable = [c for c in player.hand if c.power <= power and c.card_type != Card_Type.PEOPLE]
            if playable:
                choice = ui.ask_yes_no(f"Light: Play a card with power {power} or less?")
                if choice:
                    selected = ui.select_card(f"Select a card to play (power {power} or less):", playable)
                    if selected:
                        play_card(game, selected, ui)


def declare_end_game(game: Game_State, ui: any) -> None:
    """Active player declares end of game."""
    player = game.active_player()
    ui.message(f"{player.name} declares the end of the game!")
    game.game_ending = True
    game.ending_player = game.current_player


def calculate_scores(game: Game_State, ui: any) -> tuple[int, int]:
    """Calculate final scores for both players."""
    scores = [0, 0]

    for i, player in enumerate(game.players):
        # Points from controlled people cards
        for people in game.peoples:
            if people.owner == i:
                # Check if destroyed
                if people.destroyed:
                    # Check Deserts wonder
                    can_score = False
                    for w in player.wonders:
                        if w.name == "Deserts" and people.effective_power() <= w.effective_power():
                            can_score = True
                            break
                    if can_score:
                        points = people.effective_power()
                        scores[i] += points
                        ui.message(f"{player.name} scores {points} from {people.name} (via Deserts)")
                else:
                    points = people.effective_power()
                    # Check Seas wonder for bonus
                    for w in player.wonders:
                        if w.name == "Seas" and people.effective_power() <= w.effective_power():
                            points += 1
                            break
                    scores[i] += points
                    ui.message(f"{player.name} scores {points} from {people.name}")

        # Points from Animals and Love wonders
        for w in player.wonders:
            if w.name == "Animals" or w.name == "Love":
                points = w.effective_power() + get_wonder_power_bonus(game, i, w)
                scores[i] += points
                ui.message(f"{player.name} scores {points} from {w.name}")

    return scores[0], scores[1]


def determine_winner(game: Game_State, scores: tuple[int, int], ui: any) -> Optional[int]:
    """
    Determine the winner.
    Returns 0 or 1 for player index, None for tie (shouldn't happen with tiebreaker).
    """
    if scores[0] > scores[1]:
        return 0
    elif scores[1] > scores[0]:
        return 1
    else:
        # Tie - the player who triggered the end loses
        if game.ending_player is not None:
            return 1 - game.ending_player
        return None
