from __future__ import annotations
from pyray import *
from config import tweak
from gods.models import Card_Type
from gods.cards import get_playable_cards, get_people_cards
from gods.game import (
    create_game, setup_game, play_card, pass_turn,
    declare_end_game, calculate_scores, determine_winner,
    trigger_start_of_turn_effects
)
from gods_ui import Gods_UI
from gods_input import process_input
import gods_rendering as gr


def create_sample_decks():
    """Create two sample decks for testing."""
    all_cards = get_playable_cards(default_power=3)

    # Split cards between players (5 each for a quick test)
    # In a real game, players would draft their decks
    deck1 = all_cards[:10]
    deck2 = all_cards[10:20]

    # Set varied power levels for more interesting gameplay
    for i, card in enumerate(deck1):
        card.power = (i % 4) + 1
    for i, card in enumerate(deck2):
        card.power = (i % 4) + 2

    return deck1, deck2


def main():
    # Initialize window
    init_window(
        tweak["window_width"],
        tweak["window_height"],
        tweak["window_title"]
    )
    set_target_fps(tweak["target_fps"])

    # Create game
    deck1, deck2 = create_sample_decks()
    peoples = get_people_cards()[:3]  # Use first 3 people cards

    game = create_game(deck1, deck2, peoples)

    # Create UI
    ui = Gods_UI()
    ui.set_game(game)

    # Setup game (draw initial hands)
    setup_game(game, ui)
    ui.message("Game started! Player 1 goes first.")
    ui.message("Click a card in your hand to play it.")
    ui.message("Click Pass to draw, or End Game to trigger final round.")

    turn_started = False

    # Main loop
    while not window_should_close():
        # Trigger start-of-turn effects (like Light wonder)
        if not turn_started and not game.game_over:
            trigger_start_of_turn_effects(game, ui)
            turn_started = True

        # Process input
        result = process_input(game, ui)

        # Handle actions
        if result.play_card:
            if play_card(game, result.play_card, ui):
                game.switch_turn()
                turn_started = False

        elif result.pass_turn:
            if pass_turn(game, ui):
                game.switch_turn()
                turn_started = False

        elif result.end_game:
            declare_end_game(game, ui)
            game.switch_turn()
            turn_started = False

        # Check for game over and calculate scores
        if game.game_over and "scores" not in ui.ui_state:
            scores = calculate_scores(game, ui)
            winner = determine_winner(game, scores, ui)
            ui.ui_state["scores"] = scores
            ui.ui_state["winner"] = winner

            if winner is not None:
                ui.message(f"Player {winner + 1} wins with {scores[winner]} points!")
            else:
                ui.message("It's a tie!")

        # Draw
        begin_drawing()
        gr.draw_game(game, ui.ui_state)
        end_drawing()

    # Cleanup
    close_window()


if __name__ == "__main__":
    main()
