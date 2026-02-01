from __future__ import annotations
import random
import copy
from typing import Optional
from gods.models import Card, Card_Type, Card_Color, Player, Game_State
from gods.cards import get_playable_cards, get_people_cards
from gods.game import (
    create_game, setup_game, play_card, pass_turn, declare_end_game,
    check_people_conditions, calculate_scores, determine_winner,
    trigger_start_of_turn_effects
)


class Terminal_UI:
    """Terminal-based user interface for the game."""

    def message(self, text: str) -> None:
        print(f"  > {text}")

    def ask_yes_no(self, prompt: str) -> bool:
        while True:
            response = input(f"{prompt} (y/n): ").strip().lower()
            if response in ('y', 'yes'):
                return True
            elif response in ('n', 'no'):
                return False
            print("Please enter 'y' or 'n'.")

    def select_card(self, prompt: str, cards: list[Card]) -> Optional[Card]:
        if not cards:
            return None

        print(f"\n{prompt}")
        for i, card in enumerate(cards):
            print(f"  {i + 1}. {card.detailed_str()}")
        print(f"  0. Cancel")

        while True:
            try:
                choice = int(input("Enter choice: "))
                if choice == 0:
                    return None
                if 1 <= choice <= len(cards):
                    return cards[choice - 1]
            except ValueError:
                pass
            print(f"Please enter a number between 0 and {len(cards)}.")

    def select_multiple_targets(self, prompt: str, options: list[tuple[str, any]], max_count: int) -> list:
        if not options:
            return []

        print(f"\n{prompt}")
        for i, (label, _) in enumerate(options):
            print(f"  {i + 1}. {label}")
        print(f"  Enter numbers separated by commas (max {max_count}), or 0 to select none.")

        while True:
            try:
                response = input("Enter choices: ").strip()
                if response == '0':
                    return []

                indices = [int(x.strip()) for x in response.split(',') if x.strip()]
                if all(1 <= i <= len(options) for i in indices) and len(indices) <= max_count:
                    return [options[i - 1][1] for i in indices]
            except ValueError:
                pass
            print(f"Please enter valid numbers (1-{len(options)}), max {max_count} selections.")

    def opponent_select_discard(self, opponent: Player, count: int) -> list[Card]:
        print(f"\n{opponent.name}, select {count} card(s) to discard:")
        for i, card in enumerate(opponent.hand):
            print(f"  {i + 1}. {card}")

        while True:
            try:
                response = input("Enter choices (comma-separated): ").strip()
                indices = [int(x.strip()) for x in response.split(',') if x.strip()]
                if len(indices) == count and all(1 <= i <= len(opponent.hand) for i in indices):
                    return [opponent.hand[i - 1] for i in indices]
            except ValueError:
                pass
            print(f"Please select exactly {count} card(s).")


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
                print(f"    - {w.detailed_str()}")
        else:
            print(f"  Wonders in play: None")

        # Show hand for current player (or both in hot-seat mode)
        print(f"  Hand ({len(player.hand)} cards):")
        for card in player.hand:
            print(f"    - {card.detailed_str()}")

    print("\n" + "=" * 60)


def get_player_action(game: Game_State, ui: Terminal_UI) -> str:
    """Get the current player's action choice."""
    player = game.active_player()

    print(f"\n{player.name}'s turn. Choose an action:")
    print("  1. Play a card")
    print("  2. Pass (draw a card)")
    print("  3. End the game")
    print("  4. Show game state")

    while True:
        try:
            choice = int(input("Enter choice: "))
            if choice == 1:
                return "play"
            elif choice == 2:
                return "pass"
            elif choice == 3:
                return "end"
            elif choice == 4:
                return "show"
        except ValueError:
            pass
        print("Please enter 1, 2, 3, or 4.")


def select_deck(available_cards: list[Card], player_name: str) -> list[Card]:
    """Let a player select 10 cards for their deck."""
    print(f"\n{player_name}, select 10 cards for your deck:")

    # Group cards by type
    wonders = [c for c in available_cards if c.card_type == Card_Type.WONDER]
    events = [c for c in available_cards if c.card_type == Card_Type.EVENT]

    print("\nAvailable Wonders:")
    for i, card in enumerate(wonders):
        print(f"  W{i + 1}. {card.detailed_str()}")

    print("\nAvailable Events:")
    for i, card in enumerate(events):
        print(f"  E{i + 1}. {card.detailed_str()}")

    deck = []
    while len(deck) < 10:
        remaining = 10 - len(deck)
        print(f"\nSelected: {len(deck)}/10. Select {remaining} more cards.")
        print("Enter 'W#' for wonder or 'E#' for event (e.g., W1, E3)")
        print("Enter 'auto' to randomly fill remaining slots")

        choice = input("Enter choice: ").strip().upper()

        if choice == 'AUTO':
            remaining_cards = [c for c in available_cards if c not in deck]
            random.shuffle(remaining_cards)
            deck.extend(remaining_cards[:remaining])
            break

        try:
            if choice.startswith('W'):
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(wonders):
                    card = wonders[idx]
                    if card not in deck:
                        deck.append(copy.deepcopy(card))
                        print(f"Added {card.name} to deck.")
                    else:
                        print("Card already in deck!")
                else:
                    print("Invalid wonder number.")
            elif choice.startswith('E'):
                idx = int(choice[1:]) - 1
                if 0 <= idx < len(events):
                    card = events[idx]
                    if card not in deck:
                        deck.append(copy.deepcopy(card))
                        print(f"Added {card.name} to deck.")
                    else:
                        print("Card already in deck!")
                else:
                    print("Invalid event number.")
            else:
                print("Invalid format. Use W# or E#.")
        except (ValueError, IndexError):
            print("Invalid input.")

    return deck


def select_people_cards(all_people: list[Card]) -> list[Card]:
    """Select 3 people cards for the center."""
    print("\nSelect 3 people cards for the center:")
    for i, card in enumerate(all_people):
        print(f"  {i + 1}. {card.detailed_str()}")
    print("Enter 'auto' for random selection")

    while True:
        choice = input("Enter 3 numbers (comma-separated) or 'auto': ").strip()

        if choice.lower() == 'auto':
            selected = random.sample(all_people, 3)
            print(f"Selected: {', '.join(p.name for p in selected)}")
            return [copy.deepcopy(p) for p in selected]

        try:
            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            if len(indices) == 3 and all(0 <= i < len(all_people) for i in indices) and len(set(indices)) == 3:
                selected = [all_people[i] for i in indices]
                return [copy.deepcopy(p) for p in selected]
        except ValueError:
            pass
        print("Please enter exactly 3 different numbers.")


def quick_setup() -> tuple[list[Card], list[Card], list[Card]]:
    """Quick setup with random decks and people cards."""
    all_playable = get_playable_cards(default_power=3)
    all_people = get_people_cards(default_power=3)

    # Random decks for both players
    random.shuffle(all_playable)
    deck1 = [copy.deepcopy(c) for c in all_playable[:10]]
    deck2 = [copy.deepcopy(c) for c in all_playable[10:20]]

    # Random 3 people cards
    people = random.sample(all_people, 3)
    people = [copy.deepcopy(p) for p in people]

    return deck1, deck2, people


def main():
    print("=" * 60)
    print("        GODS - A Card Game")
    print("=" * 60)

    print("\nSetup options:")
    print("  1. Quick game (random decks)")
    print("  2. Draft decks")

    while True:
        try:
            setup_choice = int(input("Enter choice: "))
            if setup_choice in (1, 2):
                break
        except ValueError:
            pass
        print("Please enter 1 or 2.")

    if setup_choice == 1:
        deck1, deck2, people = quick_setup()
        print("\nQuick game setup complete!")
        print(f"Player 1 deck: {', '.join(c.name for c in deck1)}")
        print(f"Player 2 deck: {', '.join(c.name for c in deck2)}")
        print(f"People cards: {', '.join(p.name for p in people)}")
    else:
        all_playable = get_playable_cards(default_power=3)
        all_people = get_people_cards(default_power=3)

        people = select_people_cards(all_people)
        deck1 = select_deck(all_playable, "Player 1")
        deck2 = select_deck(all_playable, "Player 2")

    # Create and setup game
    game = create_game(deck1, deck2, people)
    ui = Terminal_UI()

    setup_game(game, ui)
    print("\nGame started! Each player has drawn 5 cards.")

    # Initial people condition check
    check_people_conditions(game, ui)

    # Main game loop
    while not game.game_over:
        display_game_state(game)

        # Trigger start of turn effects
        trigger_start_of_turn_effects(game, ui)

        action = get_player_action(game, ui)

        if action == "show":
            continue

        elif action == "play":
            player = game.active_player()
            playable = [c for c in player.hand if c.card_type in (Card_Type.WONDER, Card_Type.EVENT)]

            if not playable:
                print("No cards to play!")
                continue

            card = ui.select_card("Select a card to play:", playable)
            if card:
                play_card(game, card, ui)
                game.switch_turn()

        elif action == "pass":
            pass_turn(game, ui)
            if not game.game_over:
                game.switch_turn()

        elif action == "end":
            declare_end_game(game, ui)
            game.switch_turn()

    # Game over - calculate scores
    print("\n" + "=" * 60)
    print("GAME OVER!")
    print("=" * 60)

    display_game_state(game)

    print("\n--- FINAL SCORING ---")
    score1, score2 = calculate_scores(game, ui)

    print(f"\nFinal Scores:")
    print(f"  Player 1: {score1} points")
    print(f"  Player 2: {score2} points")

    winner = determine_winner(game, (score1, score2), ui)
    if winner is not None:
        print(f"\n{game.players[winner].name} WINS!")
    else:
        print("\nIt's a tie!")


if __name__ == "__main__":
    main()
