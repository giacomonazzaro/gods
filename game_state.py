from __future__ import annotations
import random
from models import Card, Stack, Drag_State, Game_State
from config import tweak


def create_card(id: str, title: str, description: str = "") -> Card:
    return Card(id=id, title=title, description=description)


def create_stack(x: float, y: float, spread_x: float = 0, spread_y: float = 0,
                 face_up: bool = True) -> Stack:
    return Stack(x=x, y=y, spread_x=spread_x, spread_y=spread_y, face_up=face_up)


def add_card_to_stack(card: Card, stack: Stack) -> None:
    stack.cards.append(card)
    update_card_positions(stack)


def remove_card_from_stack(card: Card, stack: Stack) -> Card | None:
    if card in stack.cards:
        stack.cards.remove(card)
        update_card_positions(stack)
        return card
    return None


def update_card_positions(stack: Stack) -> None:
    """Update x,y positions of all cards in a stack based on spread values."""
    for i, card in enumerate(stack.cards):
        card.x = stack.x + i * stack.spread_x
        card.y = stack.y + i * stack.spread_y


def move_card_to_stack(card: Card, from_stack: Stack, to_stack: Stack) -> None:
    remove_card_from_stack(card, from_stack)
    add_card_to_stack(card, to_stack)


def find_stack_containing_card(card: Card, game_state: Game_State) -> Stack | None:
    all_stacks = [game_state.draw_pile, game_state.hand, game_state.discard_pile]
    for stack in all_stacks:
        if card in stack.cards:
            return stack
    return None


def is_card_on_table(card: Card, game_state: Game_State) -> bool:
    return card in game_state.table_cards


def add_card_to_table(card: Card, game_state: Game_State) -> None:
    """Add a card to the table, keeping its current position."""
    game_state.table_cards.append(card)


def remove_card_from_table(card: Card, game_state: Game_State) -> Card | None:
    if card in game_state.table_cards:
        game_state.table_cards.remove(card)
        return card
    return None


def draw_cards(game_state: Game_State, count: int = 1) -> None:
    """Move cards from draw pile to hand."""
    for _ in range(count):
        if not game_state.draw_pile.cards:
            shuffle_discard_to_draw(game_state)
        if game_state.draw_pile.cards:
            card = game_state.draw_pile.cards.pop()
            update_card_positions(game_state.draw_pile)
            add_card_to_stack(card, game_state.hand)


def discard_hand(game_state: Game_State) -> None:
    """Move all hand cards to discard pile."""
    while game_state.hand.cards:
        card = game_state.hand.cards.pop()
        add_card_to_stack(card, game_state.discard_pile)
    update_card_positions(game_state.hand)


def discard_table(game_state: Game_State) -> None:
    """Move all table cards to discard pile."""
    while game_state.table_cards:
        card = game_state.table_cards.pop()
        add_card_to_stack(card, game_state.discard_pile)


def shuffle_discard_to_draw(game_state: Game_State) -> None:
    """Shuffle discard pile back into draw pile."""
    cards = game_state.discard_pile.cards[:]
    game_state.discard_pile.cards.clear()
    update_card_positions(game_state.discard_pile)
    random.shuffle(cards)
    for card in cards:
        add_card_to_stack(card, game_state.draw_pile)


def play_card(card: Card, x: float, y: float, game_state: Game_State) -> None:
    """Move a card from hand to table at the given position."""
    if card in game_state.hand.cards:
        remove_card_from_stack(card, game_state.hand)
        card.x = x
        card.y = y
        add_card_to_table(card, game_state)


def end_turn(game_state: Game_State) -> None:
    """End turn: discard hand and table cards, draw new hand."""
    discard_hand(game_state)
    discard_table(game_state)
    draw_cards(game_state, 5)


def create_sample_deck() -> list[Card]:
    """Create a sample deck of 10 cards."""
    card_names = [
        ("strike", "Strike", "Deal 6 damage"),
        ("defend", "Defend", "Gain 5 block"),
        ("bash", "Bash", "Deal 8 damage, apply vulnerable"),
        ("heal", "Heal", "Restore 5 health"),
        ("draw", "Draw", "Draw 2 cards"),
        ("power", "Power Up", "Gain 2 strength"),
        ("shield", "Shield", "Gain 8 block"),
        ("slash", "Slash", "Deal 10 damage"),
        ("dodge", "Dodge", "Gain 3 block, draw 1"),
        ("fury", "Fury", "Deal 4 damage twice"),
    ]
    return [create_card(id, title, desc) for id, title, desc in card_names]


def create_game_state() -> Game_State:
    """Initialize a new game state with deck builder zones."""
    draw_x, draw_y = tweak["draw_pile_pos"]
    discard_x, discard_y = tweak["discard_pile_pos"]
    hand_x, hand_y = tweak["hand_pos"]

    game_state = Game_State(
        draw_pile=create_stack(draw_x, draw_y, spread_y=tweak["pile_spread_y"], face_up=False),
        hand=create_stack(hand_x, hand_y, spread_x=tweak["hand_spread_x"]),
        discard_pile=create_stack(discard_x, discard_y, spread_y=tweak["pile_spread_y"]),
        drag_state=Drag_State()
    )

    # Add sample deck to draw pile and shuffle
    deck = create_sample_deck()
    random.shuffle(deck)
    for card in deck:
        add_card_to_stack(card, game_state.draw_pile)

    # Draw initial hand
    draw_cards(game_state, 5)

    return game_state
